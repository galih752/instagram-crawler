# Instagram Crawler

Native Instagram crawler using [instagrapi](https://github.com/subzeroid/instagrapi) with multi-output support (Kafka, NSQ, Beanstalk, File, Stdout).

> ⚠️ **Dependency:** Requires [Token Management API](../token_management_all_platform/) for Instagram session pool.  
> Run the token management service first before starting this crawler.

## Architecture

```
source/
  main.py                  CLI entry (crawler / pusher)
  config.py                Pydantic BaseSettings from .env
  controllers/
    __init__.py            Controllers(ABC) -- proxy, SSDB, Redis, I/O
    instagram/
      __init__.py          InstagramBaseController -- session mgmt
      post.py              InstagramPostController
      profile.py           InstagramProfileController
      comment.py           InstagramCommentController
  library/
    instagram/
      __init__.py          InstagramClient -- instagrapi wrapper
      mapper.py            InstagramMapper -- raw -> Pydantic
      auth.py              InstagramAuth -- token management API
  models/
    instagram.py           InstagramPost, InstagramUser, InstagramComment, InstagramHashtag
  exception/
    exception.py           Exception hierarchy + MessageException
  helpers/
    __init__.py            init_beanstalk, init_nsq, job_metadata
    eBnsq.py              NSQ HTTP producer
    html_parser.py        BS4 + PyQuery wrapper
    input/                Input facade + drivers (beanstalk, std, file)
    output/               Output facade + drivers (kafka, nsq, beanstalk, std, file)
  deployment/
    01-configmap.yaml     Kubernetes ConfigMap
    02-deployment.yaml    Kubernetes Deployment + Service
```

## Requirements

- Python 3.10+
- Redis (cache / dedup)
- SSDB (persistent dedup, Redis-protocol compatible)
- Beanstalkd (job queue)
- Kafka or NSQ (output sink)
- Token management API (Instagram session pool)

## Token Management Integration

```ini
# config.ini
[service]
token_management = http://localhost:9090
```

The crawler calls:
- `GET /api/v1/instagram/session` — acquire Instagram session
- `PUT /api/v1/instagram/session/release` — release session
- `PUT /api/v1/instagram/session/report` — report faulty session

## Installation

```bash
# Clone repository
cd instagram_crawler

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Copy environment template
cp .env.example .env
# Edit .env with real values
```

## Configuration

All configuration is read from environment variables (or a `.env` file). See `.env.example` for the full list.

Key variables:
| Variable | Description |
|---|---|
| `INSTAGRAM_TOKEN_MANAGEMENT_URL` | Token management API base URL |
| `REDIS_HOST`, `REDIS_PORT` | Redis cache connection |
| `SSDB_HOST`, `SSDB_PORT` | SSDB dedup connection |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka bootstrap servers |
| `BEANSTALK_HOST`, `BEANSTALK_PORT` | Beanstalkd connection |
| `PROXY_LIST` | Comma-separated proxy URLs |
| `SENTRY_DSN` | Sentry error tracking |

## CLI Usage

### Crawler

```bash
# Post by account
python source/main.py crawler --mode instagram --type post_by_account \
    -i beanstalk -o instagram_posts \
    --beanstalk-host localhost --beanstalk-port 11300 \
    -d kafka --bootstrap-servers localhost:9092 \
    -s beanstalk

# Post by hashtag (stdin mode)
python source/main.py crawler --mode instagram --type post_by_hashtag \
    -i travel -d std

# Post detail by code
python source/main.py crawler --mode instagram --type post_detail \
    -i CzAbCdEfGh -d std

# Fetch profile
python source/main.py crawler --mode instagram --type profile \
    -i nike -d std

# Search profiles
python source/main.py crawler --mode instagram --type search_profile \
    -i travelblogger -d std

# Fetch comments
python source/main.py crawler --mode instagram --type comment \
    -i beanstalk -o instagram_comments \
    --beanstalk-host localhost --beanstalk-port 11300 \
    -d kafka --bootstrap-servers localhost:9092 \
    -s beanstalk
```

### Crawl types reference

| Type | Description | Input |
|---|---|---|
| `post_by_account` | Fetch recent posts for a username | `{"username": "..."}` |
| `post_by_hashtag` | Fetch recent posts for a hashtag | `{"hashtag": "..."}` |
| `post_by_keyword` | Search posts by keyword | `{"keyword": "..."}` |
| `post_detail` | Fetch single post by ID/URL | `{"media_id": "..."}` |
| `profile` | Fetch user profile | `{"username": "..."}` |
| `search_profile` | Search users | `{"query": "..."}` |
| `comment` | Fetch comments for a post | `{"media_id": "..."}` |
| `comment_reply` | Fetch replies to a comment | `{"media_id": "...", "comment_id": "..."}` |

### Pusher

```bash
python source/main.py pusher --mode instagram --type post_by_account \
    -i beanstalk -o my_tube \
    --beanstalk-host localhost --beanstalk-port 11300 \
    -d beanstalk -s beanstalk
```

## Docker

```bash
# Build
docker build -t instagram-crawler:latest .

# Run
docker run --rm -it \
    -e INSTAGRAM_TOKEN_MANAGEMENT_URL=http://token-api:8000 \
    -e REDIS_HOST=redis \
    instagram-crawler:latest \
    crawler --mode instagram --type post_by_hashtag -i travel -d std
```

## Kubernetes

```bash
kubectl apply -f source/deployment/01-configmap.yaml
kubectl apply -f source/deployment/02-deployment.yaml
```

## Output drivers

| Driver | Flag | Description |
|---|---|---|
| `std` | `-d std` | Print to stdout (default) |
| `kafka` | `-d kafka` | Publish to Kafka topic |
| `nsq` | `-d nsq` | Publish to NSQ topic |
| `beanstalk` | `-d beanstalk` | Put into Beanstalk tube |
| `file` | `-d file` | Append to file |

## Input drivers

| Driver | Flag | Description |
|---|---|---|
| `std` | `-s std` (default) | Single keyword from `-i` |
| `beanstalk` | `-s beanstalk` | Read from Beanstalk tube |
| `file` | `-s file` | Read lines from file |
