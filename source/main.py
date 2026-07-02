#!/usr/bin/env python3
"""
Instagram Crawler CLI.

Usage::

    # Crawl posts by account
    python source/main.py crawler --mode instagram --type post_by_account \\
        -i beanstalk -o instagram_posts \\
        --beanstalk-host localhost --beanstalk-port 11300 \\
        -d kafka --bootstrap-servers localhost:9092 \\
        -s beanstalk

    # Crawl post detail by code
    python source/main.py crawler --mode instagram --type post_detail \\
        -i CzAbCdEfGh

    # Push pre-fetched jobs into a tube
    python source/main.py pusher --mode instagram --type post_by_account \\
        -i beanstalk -o my_tube \\
        --beanstalk-host localhost --beanstalk-port 11300 \\
        -d beanstalk -s beanstalk
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Instagram crawler using instagrapi",
    )
    parser.add_argument(
        "-c", "--config",
        dest="config",
        type=str,
        default="config.ini",
        help="Path to config.ini",
    )
    parser.add_argument(
        "-s", "--source",
        dest="source",
        type=str,
        help="Source type (beanstalk, file, std)",
    )
    parser.add_argument(
        "-d", "--destination",
        dest="destination",
        type=str,
        help="Destination type (kafka, nsq, beanstalk, file, std)",
    )
    parser.add_argument(
        "-i", "--input",
        dest="input",
        type=str,
        help="Input identifier (tube name, file path, or keyword)",
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        type=str,
        help="Output identifier (topic name, tube name, or file path)",
    )
    parser.add_argument(
        "--beanstalk-host",
        dest="beanstalk_host",
        type=str,
        help="Beanstalkd host",
    )
    parser.add_argument(
        "--beanstalk-port",
        dest="beanstalk_port",
        type=int,
        help="Beanstalkd port",
    )
    parser.add_argument(
        "--bootstrap-servers",
        dest="bootstrap_servers",
        type=str,
        help="Kafka bootstrap servers (comma-separated)",
    )
    parser.add_argument(
        "--nsqd-http-address",
        dest="nsqd_http_address",
        type=str,
        help="NSQ HTTP publish address",
    )
    parser.add_argument(
        "--cache",
        dest="cache",
        type=str,
        default="false",
        help="Enable Redis cache (true/false)",
    )

    sub = parser.add_subparsers(title="action", dest="which", help="Action to perform")

    # ---- crawler ----
    crawler = sub.add_parser("crawler", help="Run a crawler")
    crawler.add_argument("--mode", dest="mode", type=str, required=True)
    crawler.add_argument("--type", dest="type", type=str, required=True)
    crawler.add_argument("--cookies-type", dest="cookies_type", type=str, default="post")
    crawler.add_argument("--tube-comment", dest="tube_comment", type=str)
    crawler.add_argument("--tube-replies", dest="tube_replies", type=str)
    crawler.add_argument("--ssdb-host", dest="ssdb_host", type=str)
    crawler.add_argument("--ssdb-port", dest="ssdb_port", type=int)

    # ---- pusher ----
    pusher = sub.add_parser("pusher", help="Push jobs into a queue")
    pusher.add_argument("--mode", dest="mode", type=str, required=True)
    pusher.add_argument("--type", dest="type", type=str, required=True)

    return parser


def dispatch_crawler(args: argparse.Namespace) -> Any:
    """Import and instantiate the correct controller based on args."""
    mode = args.mode
    crawl_type = args.type
    kwargs = vars(args).copy()

    if mode == "instagram":
        if crawl_type in ("post_by_account", "post_by_hashtag", "post_by_keyword", "post_detail"):
            from controllers.instagram.post import InstagramPostController
            return InstagramPostController(**kwargs)
        elif crawl_type == "profile":
            from controllers.instagram.profile import InstagramProfileController
            return InstagramProfileController(**kwargs)
        elif crawl_type == "search_profile":
            from controllers.instagram.profile import InstagramProfileController
            return InstagramProfileController(**kwargs)
        elif crawl_type in ("comment", "comment_reply"):
            from controllers.instagram.comment import InstagramCommentController
            return InstagramCommentController(**kwargs)
        else:
            print(f"Unknown instagram type: {crawl_type}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)


def dispatch_pusher(args: argparse.Namespace) -> Any:
    """Import and instantiate the correct pusher controller."""
    mode = args.mode
    kwargs = vars(args).copy()

    if mode == "instagram":
        # Pusher typically re-uses the same controller classes but
        # with different input/output wiring; the handler decides.
        from controllers.instagram.post import InstagramPostController
        return InstagramPostController(**kwargs)
    else:
        print(f"Unknown pusher mode: {mode}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.which:
        parser.print_help()
        sys.exit(0)

    if args.which == "crawler":
        controller = dispatch_crawler(args)
    elif args.which == "pusher":
        controller = dispatch_pusher(args)
    else:
        parser.print_help()
        sys.exit(0)

    asyncio.run(controller.main())


if __name__ == "__main__":
    main()
