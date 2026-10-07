from minio import Minio


class MinioClient:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket
