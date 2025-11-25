"""
Embedding generation utilities using OpenAI
"""
import os
import time
import logging
from typing import List
import openai

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings using OpenAI's API"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 100,
        max_retries: int = 3
    ):
        """
        Initialize embedding generator

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model to use
            dimensions: Embedding dimensions
            batch_size: Max texts to embed in one API call
            max_retries: Max retry attempts on failure
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        openai.api_key = self.api_key
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_retries = max_retries

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            logger.debug(f"Generating embeddings for batch {i // self.batch_size + 1}")

            embeddings = await self._generate_batch(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts with retry logic"""
        retry_delay = 1.0

        for attempt in range(self.max_retries):
            try:
                response = openai.embeddings.create(
                    model=self.model,
                    input=texts
                )
                return [item.embedding for item in response.data]

            except openai.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Rate limit hit, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed after {self.max_retries} attempts: {e}")
                    raise

            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed to generate embeddings: {e}")
                    # Fallback: try one by one
                    return await self._generate_individually(texts)

        # Shouldn't reach here
        return [[0.0] * self.dimensions for _ in texts]

    async def _generate_individually(self, texts: List[str]) -> List[List[float]]:
        """Fallback: generate embeddings one by one"""
        logger.info("Falling back to individual embedding generation")
        embeddings = []

        for i, text in enumerate(texts):
            try:
                response = openai.embeddings.create(
                    model=self.model,
                    input=[text]
                )
                embeddings.append(response.data[0].embedding)
            except Exception as e:
                logger.error(f"Failed to embed text {i}: {e}")
                # Zero vector as fallback
                embeddings.append([0.0] * self.dimensions)

        return embeddings

    async def generate_single(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else [0.0] * self.dimensions
