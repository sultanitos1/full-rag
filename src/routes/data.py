from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request, Form, File
from typing import List
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProcessController, NLPController
import aiofiles
from models import ResponseSignal
import logging
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.db_schemes import DataChunk, Asset
from models.enums.AssetTypeEnum import AssetTypeEnum
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


@data_router.post("/multi-upload")
async def upload_multiple_files(
    request: Request,
    files: List[UploadFile] = File(...),
    chunk_size: Optional[int] = Form(500),
    overlap_size: Optional[int] = Form(20),
    app_settings: Settings = Depends(get_settings)
):

    data_controller = DataController()
    overall_results = []
    succeeded = 0
    failed = 0

    for file in files:
        result_entry = {"file_name": file.filename}

        is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
        if not is_valid:
            result_entry["status"] = "error"
            result_entry["error"] = result_signal
            overall_results.append(result_entry)
            failed += 1
            continue

        file_path, file_id = data_controller.generate_unique_filepath(
            orig_file_name=file.filename,
        )

        try:
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                    await f.write(chunk)
        except Exception as e:
            logger.error(f"Error while uploading file {file.filename}: {e}")
            result_entry["status"] = "error"
            result_entry["error"] = ResponseSignal.FILE_UPLOAD_FAILED.value
            overall_results.append(result_entry)
            failed += 1
            continue

        asset_model = await AssetModel.create_instance(
            db_client=request.app.db_client
        )

        asset_resource = Asset(
            asset_type=AssetTypeEnum.FILE.value,
            asset_name=file_id,
            asset_size=os.path.getsize(file_path),
            asset_config={"city": app_settings.DEFAULT_CITY, "doc_type": app_settings.DEFAULT_DOC_TYPE}
        )

        asset_record = await asset_model.create_asset(asset=asset_resource)
        if not asset_record or not asset_record.id:
            logger.error(f"Failed to create asset record for {file.filename}")
            result_entry["status"] = "error"
            result_entry["error"] = "asset_creation_failed"
            overall_results.append(result_entry)
            failed += 1
            continue

        process_controller = ProcessController()
        chunk_model = await ChunkModel.create_instance(
            db_client=request.app.db_client
        )

        chunk_metadata = {
            "city": app_settings.DEFAULT_CITY,
            "doc_type": app_settings.DEFAULT_DOC_TYPE,
            "asset_id": str(asset_record.id),
        }

        file_content = process_controller.get_file_content(file_id=asset_record.asset_name)
        inserted_chunks = 0

        if file_content:
            file_chunks = process_controller.process_file_content(
                file_content=file_content,
                file_id=asset_record.asset_name,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
                metadata=chunk_metadata
            )

            if file_chunks:
                chunk_records = [
                    DataChunk(
                        chunk_text=chunk.page_content,
                        chunk_metadata=chunk.metadata,
                        chunk_order=i+1,
                    )
                    for i, chunk in enumerate(file_chunks)
                ]
                inserted_chunks = await chunk_model.insert_many_chunks(chunks=chunk_records)

                # index into Qdrant
                nlp_controller = NLPController(
                    vectordb_client=request.app.vectordb_client,
                    generation_client=request.app.generation_client,
                    embedding_client=request.app.embedding_client,
                    template_parser=request.app.template_parser,
                )
                nlp_controller.index_chunks(chunks=chunk_records)

        result_entry["status"] = "success"
        result_entry["file_id"] = str(asset_record.id)
        result_entry["inserted_chunks"] = inserted_chunks
        overall_results.append(result_entry)
        succeeded += 1

    total = len(files)
    if failed == 0:
        signal = ResponseSignal.MULTI_UPLOAD_SUCCESS.value
    elif succeeded == 0:
        signal = ResponseSignal.MULTI_UPLOAD_FAILED.value
    else:
        signal = ResponseSignal.MULTI_UPLOAD_PARTIAL.value

    return JSONResponse(content={
        "signal": signal,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "results": overall_results,
    })


@data_router.get("/files")
async def list_files(request: Request):

    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    records = await asset_model.collection.find(
        {}, {"_id": 1, "asset_name": 1, "asset_size": 1, "asset_pushed_at": 1}
    ).sort("asset_pushed_at", -1).to_list(length=None)

    assets = [
        {
            "file_id": str(r["_id"]),
            "asset_name": r.get("asset_name"),
            "file_size": r.get("asset_size"),
            "uploaded_at": r.get("asset_pushed_at").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Africa/Cairo")).isoformat() if r.get("asset_pushed_at") else None,
        }
        for r in records
    ]

    return JSONResponse(content={"assets": assets})


@data_router.put("/file/{file_id}")
async def update_file(
    request: Request,
    file_id: str,
    file: UploadFile,
    chunk_size: Optional[int] = Form(500),
    overlap_size: Optional[int] = Form(20),
    app_settings: Settings = Depends(get_settings),
):

    data_controller = DataController()

    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": result_signal}
        )

    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    asset = await asset_model.get_asset_by_id(asset_id=file_id)
    if not asset:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": "file_not_found", "message": "No file found with this ID."}
        )

    old_file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets/files",
        asset.asset_name
    )

    # delete old file from disk
    if os.path.exists(old_file_path):
        os.remove(old_file_path)

    # save new file with same asset_name
    new_file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets/files",
        asset.asset_name
    )

    try:
        async with aiofiles.open(new_file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error while saving updated file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value}
        )

    # update asset record
    await asset_model.collection.update_one(
        {"_id": ObjectId(file_id) if isinstance(file_id, str) else file_id},
        {"$set": {
            "asset_size": os.path.getsize(new_file_path),
            "asset_pushed_at": datetime.now(ZoneInfo("Africa/Cairo")),
        }}
    )

    # delete old chunks + vectors
    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.db_client
    )
    _ = await chunk_model.delete_chunks_by_asset_id(asset_id=file_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )
    _ = nlp_controller.delete_file_vectors(asset_id=file_id)

    # re-process + re-index
    process_controller = ProcessController()
    file_content = process_controller.get_file_content(file_id=asset.asset_name)
    inserted_chunks = 0

    config = asset.asset_config or {}
    chunk_metadata = {
        "city": config.get("city", app_settings.DEFAULT_CITY),
        "doc_type": config.get("doc_type", app_settings.DEFAULT_DOC_TYPE),
        "asset_id": file_id,
    }

    if file_content:
        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=asset.asset_name,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            metadata=chunk_metadata
        )

        if file_chunks:
            chunk_records = [
                DataChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=i+1,
                )
                for i, chunk in enumerate(file_chunks)
            ]
            inserted_chunks = await chunk_model.insert_many_chunks(chunks=chunk_records)

            nlp_controller.index_chunks(chunks=chunk_records)

    return JSONResponse(content={
        "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
        "file_id": file_id,
        "inserted_chunks": inserted_chunks,
    })


@data_router.delete("/file/{file_id}")
async def delete_file(request: Request, file_id: str):

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    asset = await asset_model.delete_asset_by_id(asset_id=file_id)

    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.db_client
    )

    _ = await chunk_model.delete_chunks_by_asset_id(asset_id=file_id)

    _ = nlp_controller.delete_file_vectors(asset_id=file_id)

    return JSONResponse(
        content={"signal": ResponseSignal.DELETE_SUCCESS.value}
    )
