from app.services.ingestion_service import IngestionService
from app.settings import Settings


def main() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    ingestion_service = IngestionService(mode="historical", settings=settings)


if __name__ == "__main__":
    main()
