"""
Text chunking utilities for breaking down documents into manageable pieces
"""
import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class TextChunk:
    """Represents a chunk of text from a document"""
    content: str
    chunk_index: int
    total_chunks: int
    char_start: int
    char_end: int


class TextChunker:
    """Chunks text intelligently based on headers and size limits"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        """
        Initialize chunker

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
            min_chunk_size: Minimum size for a chunk
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_markdown(self, text: str) -> List[TextChunk]:
        """
        Chunk markdown text intelligently by headers and size

        Args:
            text: Markdown text to chunk

        Returns:
            List of TextChunk objects
        """
        if not text or len(text) < self.min_chunk_size:
            return [TextChunk(
                content=text,
                chunk_index=0,
                total_chunks=1,
                char_start=0,
                char_end=len(text)
            )]

        # Try to split by headers first
        chunks = self._split_by_headers(text)

        # If chunks are too large, further split them
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size * 1.5:
                # Split large chunks by paragraphs
                sub_chunks = self._split_by_paragraphs(chunk)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        # Create TextChunk objects with metadata
        total = len(final_chunks)
        result = []
        char_pos = 0

        for i, content in enumerate(final_chunks):
            result.append(TextChunk(
                content=content.strip(),
                chunk_index=i,
                total_chunks=total,
                char_start=char_pos,
                char_end=char_pos + len(content)
            ))
            char_pos += len(content)

        return result

    def _split_by_headers(self, text: str) -> List[str]:
        """Split text by markdown headers"""
        # Match markdown headers (# Header, ## Header, etc.)
        header_pattern = r'^(#{1,6})\s+(.+)$'

        chunks = []
        current_chunk = []
        current_size = 0

        for line in text.split('\n'):
            line_with_newline = line + '\n'
            line_size = len(line_with_newline)

            # Check if this is a header
            if re.match(header_pattern, line.strip(), re.MULTILINE):
                # If we have content and we're over min size, save the chunk
                if current_chunk and current_size >= self.min_chunk_size:
                    chunks.append(''.join(current_chunk))
                    # Add overlap
                    if self.chunk_overlap > 0 and len(current_chunk) > 0:
                        overlap_text = ''.join(current_chunk[-3:])  # Last 3 lines
                        if len(overlap_text) <= self.chunk_overlap:
                            current_chunk = [overlap_text]
                            current_size = len(overlap_text)
                        else:
                            current_chunk = []
                            current_size = 0
                    else:
                        current_chunk = []
                        current_size = 0

            # Add line to current chunk
            current_chunk.append(line_with_newline)
            current_size += line_size

            # If chunk is getting too large, try to split at next paragraph
            if current_size >= self.chunk_size:
                # Look ahead for paragraph break
                if line.strip() == '':
                    chunks.append(''.join(current_chunk))
                    current_chunk = []
                    current_size = 0

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(''.join(current_chunk))

        return chunks if chunks else [text]

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraphs when too large"""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para) + 2  # +2 for the newlines

            # If single paragraph is larger than chunk_size, split it
            if para_size > self.chunk_size * 1.5:
                # Save current chunk if any
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Split the large paragraph by sentences
                sentences = re.split(r'([.!?]+\s+)', para)
                sentence_chunk = []
                sentence_size = 0

                for sentence in sentences:
                    if sentence_size + len(sentence) > self.chunk_size:
                        if sentence_chunk:
                            chunks.append(''.join(sentence_chunk))
                        sentence_chunk = [sentence]
                        sentence_size = len(sentence)
                    else:
                        sentence_chunk.append(sentence)
                        sentence_size += len(sentence)

                if sentence_chunk:
                    chunks.append(''.join(sentence_chunk))

            # If adding this paragraph would exceed chunk_size, start new chunk
            elif current_size + para_size > self.chunk_size:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))

                # Add overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap = current_chunk[-1]
                    if len(overlap) <= self.chunk_overlap:
                        current_chunk = [overlap, para]
                        current_size = len(overlap) + para_size
                    else:
                        current_chunk = [para]
                        current_size = para_size
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        # Don't forget the last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks if chunks else [text]
