"""
Command-line interface for running the mock server.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import List, Optional

from pygovpub.config import config
from pygovpub.mock import start_mock_server, stop_mock_server


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="PyGovPub Mock Server"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level (default: info)"
    )
    parser.add_argument(
        "--latency",
        type=int,
        default=None,
        help="Simulated latency in milliseconds (default: from config)"
    )
    parser.add_argument(
        "--rate-limits",
        action="store_true",
        help="Simulate API rate limits"
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Enable recording mode (requires API keys)"
    )
    parser.add_argument(
        "--fixtures",
        type=str,
        default=None,
        help="Path to fixtures directory (default: from config)"
    )
    
    return parser.parse_args(args)


async def run_server(args: argparse.Namespace) -> None:
    """Run the mock server.
    
    Args:
        args: Command-line arguments
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("pygovpub.mock")
    
    # Update configuration from command-line arguments
    if args.latency is not None:
        os.environ["PYGOVPUB_MOCK_LATENCY_MS"] = str(args.latency)
    
    if args.rate_limits:
        os.environ["PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS"] = "true"
    
    if args.record:
        os.environ["PYGOVPUB_MOCK_RECORD_MODE"] = "true"
    
    if args.fixtures:
        os.environ["PYGOVPUB_MOCK_FIXTURES_PATH"] = args.fixtures
    
    os.environ["PYGOVPUB_MOCK_ENABLED"] = "true"
    
    # Show settings
    logger.info(f"Starting mock server on {args.host}:{args.port}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Latency: {config.mock.latency_ms}ms")
    logger.info(f"Rate limits: {config.mock.simulate_rate_limits}")
    logger.info(f"Record mode: {config.mock.record_mode}")
    logger.info(f"Fixtures path: {config.mock.fixtures_path}")
    
    # Start the server
    await start_mock_server(
        host=args.host,
        port=args.port,
        log_level=args.log_level
    )
    
    # Set up signal handlers
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    logger.info(f"Mock server running at http://{args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop")
    
    # Keep the server running
    while True:
        await asyncio.sleep(1)


async def shutdown() -> None:
    """Shutdown the server gracefully."""
    logger = logging.getLogger("pygovpub.mock")
    logger.info("Shutting down mock server...")
    
    await stop_mock_server()
    
    logger.info("Mock server stopped")
    asyncio.get_event_loop().stop()


def start_mock_server_cli() -> None:
    """Entry point for the mock server CLI."""
    args = parse_args()
    
    try:
        asyncio.run(run_server(args))
    except KeyboardInterrupt:
        print("\nShutting down mock server...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)