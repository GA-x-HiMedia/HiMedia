"""
Simple command-line entry point.

Usage:
    python -m src.rag.main ingest
    python -m src.rag.main query "What does an editor's role allow?"
    python -m src.rag.main            # interactive question loop
"""
import sys

from .ingest import run_ingest
from .query import format_sources, generate_answer


def run_query(question: str) -> None:
    """Answer one question and print it with its sources."""
    result = generate_answer(question)
    print("\nAnswer:")
    print(result.answer)
    print("\nSources:")
    print(format_sources(result.sources) or "- none")


def run_interactive() -> None:
    """Ask questions in a loop until the user quits."""
    print("Type a question, or 'quit' to exit.")
    while True:
        question = input("\n> ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if question:
            run_query(question)


def main() -> None:
    args = sys.argv[1:]

    if not args:
        run_interactive()
    elif args[0] == "ingest":
        run_ingest()
    elif args[0] == "query" and len(args) > 1:
        run_query(" ".join(args[1:]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()