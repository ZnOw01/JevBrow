"""Command line runner for the optional local-model autonomous agent."""

import argparse

from .agent import Agent


def main():
    parser = argparse.ArgumentParser(description="Run JevBrow with the configured local OpenAI-compatible model.")
    parser.add_argument("--url", required=True, help="http(s) page to open in the local browser")
    parser.add_argument("--goal", action="append", required=True, help="Task goal; repeat for multiple ordered goals")
    args = parser.parse_args()

    with Agent(args.url, args.goal) as agent:
        for state in agent.run():
            print(f"{state['elapsed_ms']:>5} ms  {len(state['history'])} actions  {state['status']}")
        print(state["page"]["url"])


if __name__ == "__main__":
    main()
