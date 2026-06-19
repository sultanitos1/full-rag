from .BaseController import BaseController
import os
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import CSVLoader
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import ProcessingEnum


class ProcessController(BaseController):

    def __init__(self):
        super().__init__()

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]

    def get_file_loader(self, file_id: str):

        file_ext = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(
            self.files_dir,
            file_id
        )

        if not os.path.exists(file_path):
            return None

        loaders = {
            ProcessingEnum.TXT.value: TextLoader,
            ProcessingEnum.PDF.value: PyMuPDFLoader,
            ProcessingEnum.CSV.value: CSVLoader,
            ProcessingEnum.DOCX.value: Docx2txtLoader,
        }

        loader_class = loaders.get(file_ext)
        if not loader_class:
            return None

        if file_ext == ProcessingEnum.TXT.value:
            return loader_class(file_path, encoding="utf-8")

        if file_ext == ProcessingEnum.CSV.value:
            return loader_class(file_path)

        return loader_class(file_path)

    def get_file_content(self, file_id: str):

        loader = self.get_file_loader(file_id=file_id)
        if loader:
            return loader.load()

        return None

    def process_file_content(self, file_content: list, file_id: str,
                            chunk_size: int = 100, overlap_size: int = 20,
                            metadata: dict = None):

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len,
        )

        file_content_texts = [
            rec.page_content
            for rec in file_content
        ]

        file_content_metadata = [
            rec.metadata
            for rec in file_content
        ]

        chunks = text_splitter.create_documents(
            file_content_texts,
            metadatas=file_content_metadata
        )

        if metadata:
            for chunk in chunks:
                chunk.metadata.update(metadata)

        return chunks