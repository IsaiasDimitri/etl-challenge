from app.db import source_engine
from app.models.source import SourceBase


def main() -> None:
    SourceBase.metadata.create_all(bind=source_engine)


if __name__ == "__main__":
    main()
