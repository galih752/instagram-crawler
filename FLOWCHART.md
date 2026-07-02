# Instagram Crawler — Flow Chart

> Gunakan VSCode extension **Markdown Preview Mermaid** atau [Mermaid Live Editor](https://mermaid.live) untuk melihat diagram.

---

## 1. CLI Entry Point & Dispatch

```mermaid
graph TD
    START(["python source/main.py"]) --> PARSE["Argparse: build_parser()"]
    PARSE --> SUB{"args.which?"}

    SUB -->|crawler| DISPATCH_CRAWL["dispatch_crawler()"]
    SUB -->|pusher| DISPATCH_PUSH["dispatch_pusher()"]
    SUB -->|tidak ada| HELP["print_help()"]

    DISPATCH_CRAWL --> MODE{"args.mode?"}
    MODE -->|instagram| CRAWL_TYPE{"args.type?"}

    CRAWL_TYPE -->|"post_by_account, post_by_hashtag, post_by_keyword, post_detail"| POST_CTRL["InstagramPostController"]
    CRAWL_TYPE -->|"profile, search_profile"| PROFILE_CTRL["InstagramProfileController"]
    CRAWL_TYPE -->|"comment, comment_reply"| COMMENT_CTRL["InstagramCommentController"]

    POST_CTRL --> MAIN_LOOP
    PROFILE_CTRL --> MAIN_LOOP
    COMMENT_CTRL --> MAIN_LOOP

    DISPATCH_PUSH --> PUSH_CTRL["InstagramPostController"]
    PUSH_CTRL --> MAIN_LOOP

    MAIN_LOOP["asyncio.run(controller.main())"]
```

---

## 2. Controller Initialization (Base Constructor)

```mermaid
graph TD
    INIT(["Controllers.__init__(**kwargs)"]) --> CONFIG["Load config.ini via ConfigParser"]
    CONFIG --> PROXY["Parse static proxy dari section proxy"]
    PROXY --> INPUT_FACTORY{"Input driver?"}

    INPUT_FACTORY -->|"beanstalk_host + beanstalk_port"| BEAN_IN["BeanstalkInputDriver"]
    INPUT_FACTORY -->|"file path exists"| FILE_IN["FileInputDriver"]
    INPUT_FACTORY -->|default| STD_IN["StdInputDriver"]

    BEAN_IN --> OUTPUT_FACTORY
    FILE_IN --> OUTPUT_FACTORY
    STD_IN --> OUTPUT_FACTORY

    OUTPUT_FACTORY{"Output driver?"}

    OUTPUT_FACTORY -->|"-d kafka"| KAFKA["KafkaOutputDriver"]
    OUTPUT_FACTORY -->|"-d nsq"| NSQ["NsqOutputDriver"]
    OUTPUT_FACTORY -->|"-d beanstalk"| BEAN_OUT["BeanstalkOutputDriver"]
    OUTPUT_FACTORY -->|"-d file"| FILE_OUT["FileOutputDriver"]
    OUTPUT_FACTORY -->|"-d std"| STD_OUT["StdOutputDriver"]

    KAFKA --> SSDB["Init SSDB - Redis protocol"]
    NSQ --> SSDB
    BEAN_OUT --> SSDB
    FILE_OUT --> SSDB
    STD_OUT --> SSDB

    SSDB --> REDIS["Init Redis connection"]
    REDIS --> DONE(["Controller ready"])
```

---

## 3. Main Loop

```mermaid
graph TD
    MAIN(["controller.main()"]) --> HAS_INPUT{"Has input driver?"}

    HAS_INPUT -->|YES| ITER["for job in self.input:"]
    HAS_INPUT -->|NO| DIRECT["await handler(job={})"]

    ITER --> JOB_CHECK{"job not empty?"}
    JOB_CHECK -->|YES| HANDLER["await handler(job)"]
    JOB_CHECK -->|NO| NEXT["continue / next iterasi"]

    HANDLER --> TRY["try block"]
    TRY --> HANDLER_OK["handler() completes"]
    TRY --> HANDLER_ERR["Exception raised"]

    HANDLER_OK --> FINALLY["finally: release_session()"]
    HANDLER_ERR --> EXC_HANDLER["exceptions_handler(e)"]
    EXC_HANDLER --> FINALLY

    FINALLY --> NEXT
    NEXT --> ITER

    DIRECT --> TRY
```

---

## 4. Authentication & Session Lifecycle

```mermaid
graph TD
    LOGIN_START(["logging_in()"]) --> GET_SESSION["GET /api/v1/instagram/session"]
    GET_SESSION --> PARSE_SESSION["Parse session_id dari response"]
    PARSE_SESSION --> EXTRACT_USER["Extract user PK dari session_id"]
    EXTRACT_USER --> LOGIN_CALL["login_by_sessionid(session_id, user)"]

    LOGIN_CALL --> CREATE_CLIENT["Buat instagrapi.Client()"]
    CREATE_CLIENT --> SESSION_LOGIN["client.login_by_sessionid()"]
    SESSION_LOGIN --> PATCH_CLIENT["Patch helper: media_id / media_user"]
    PATCH_CLIENT --> LOGIN_DONE(["Client ready"])

    LOGIN_DONE -->|"error: ChallengeRequired"| REPORT_C["report_session()"]
    LOGIN_DONE -->|"error: LoginRequired"| REPORT_L["report_session()"]

    REPORT_C --> RETRY{"retry < 3?"}
    REPORT_L --> RETRY
    RETRY -->|YES| GET_SESSION
    RETRY -->|NO| FAIL(["Max retries, job failed"])

    RELEASE(["release_session()"]) --> RELEASE_API["PUT /api/v1/instagram/session/release"]
    RELEASE_API --> NULLIFY["account=None, client=None"]
```

---

## 5. Post Crawling Flow

```mermaid
graph TD
    POST_START(["handler(job)"]) --> TYPE_DISPATCH{"job.type?"}

    TYPE_DISPATCH -->|post_by_account| BY_ACC
    TYPE_DISPATCH -->|post_by_hashtag| BY_TAG
    TYPE_DISPATCH -->|post_by_keyword| BY_KEY
    TYPE_DISPATCH -->|post_detail| DETAIL

    subgraph account ["post_by_account"]
        BY_ACC["get_posts_by_account()"] --> ACC_LOGIN["logging_in()"]
        ACC_LOGIN --> ACC_USER["client.user_info_by_username()"]
        ACC_USER --> ACC_MEDIA["client.user_medias_v1(user_id, amount)"]
        ACC_MEDIA --> ACC_LOOP["Loop: for media in medias"]
    end

    subgraph hashtag ["post_by_hashtag"]
        BY_TAG["get_posts_by_hashtag()"] --> TAG_LOGIN["logging_in()"]
        TAG_LOGIN --> TAG_MEDIA["client.hashtag_medias_recent(name, amount)"]
        TAG_MEDIA --> TAG_LOOP["Loop: for media in medias"]
    end

    subgraph keyword ["post_by_keyword"]
        BY_KEY["get_posts_by_keyword()"] --> KEY_LOGIN["logging_in()"]
        KEY_LOGIN --> KEY_SEARCH["Try client.fbsearch()"]
        KEY_SEARCH -->|fail| KEY_FALLBACK["Fallback: client.search_top()"]
        KEY_FALLBACK --> KEY_LOOP["Loop: for media in medias"]
        KEY_SEARCH -->|ok| KEY_LOOP
    end

    subgraph detail ["post_detail"]
        DETAIL["get_post_detail()"] --> DETAIL_RESOLVE["Resolve media_id dari URL/code"]
        DETAIL_RESOLVE --> DETAIL_LOGIN["logging_in()"]
        DETAIL_LOGIN --> DETAIL_INFO["client.media_info_v1(media_pk)"]
        DETAIL_INFO --> DETAIL_DONE["Single post ke output + SSDB"]
    end

    ACC_LOOP --> PROC_POST
    TAG_LOOP --> PROC_POST
    KEY_LOOP --> PROC_POST

    PROC_POST["Process tiap media"] --> RAW["Convert ke dict"]
    RAW --> MODEL["InstagramPost.from_instagrapi_post()"]
    MODEL --> DUMP["post.model_dump(mode='json')"]
    DUMP --> ENRICH["Tambahkan type, media_tags, metadata"]
    ENRICH --> OUTPUT["self.output.put(json)"]
    OUTPUT --> SSDB_CHECK["store_to_ssdb() - hexists + hset"]

    SSDB_CHECK --> COMMENT_CHECK{"comment_count > 0?"}
    COMMENT_CHECK -->|YES| PUSH_COMMENT["Push comment_job ke tube_comment"]
    COMMENT_CHECK -->|NO| NEXT_POST["Next post"]

    PUSH_COMMENT --> NEXT_POST
```

---

## 6. Comment Crawling Flow

```mermaid
graph TD
    COMMENT_START(["handler(job)"]) --> COMMENT_DISPATCH{"job.type?"}

    COMMENT_DISPATCH -->|get_comments| GET_COM
    COMMENT_DISPATCH -->|get_comment_replies| GET_REPLY

    subgraph comments ["get_comments"]
        GET_COM["get_comments()"] --> COM_LOGIN["logging_in()"]
        COM_LOGIN --> COM_FETCH["media_comments_pagination()"]
        COM_FETCH --> COM_LOOP["Loop: for comment in comments"]

        COM_LOOP --> COM_MODEL["InstagramComment.from_instagrapi_comment()"]
        COM_MODEL --> COM_REDIS_CHECK{"cache AND redis.exists?"}
        COM_REDIS_CHECK -->|"YES (duplicate)"| COM_SKIP["Skip"]
        COM_REDIS_CHECK -->|"NO (new)"| COM_OUTPUT["self.output.put(json)"]

        COM_OUTPUT --> COM_REDIS_SET["redis.setex(key, 4 hari)"]
        COM_REDIS_SET --> COM_REPLY_CHECK{"reply_count > 0?"}
        COM_REPLY_CHECK -->|YES| COM_CHAIN["Push reply_job ke tube_replies"]
        COM_REPLY_CHECK -->|NO| COM_NEXT["Next comment"]

        COM_SKIP --> COM_NEXT
        COM_CHAIN --> COM_NEXT

        COM_NEXT --> COM_PAGE_CHECK{"has_more AND not cache?"}
        COM_PAGE_CHECK -->|YES| COM_REQUEUE["Re-enqueue next_job dengan pagination_key baru"]
        COM_PAGE_CHECK -->|NO| COM_DONE(["Done"])
    end

    subgraph replies ["get_comment_replies"]
        GET_REPLY["get_comment_replies()"] --> REPLY_LOGIN["logging_in()"]
        REPLY_LOGIN --> REPLY_FETCH["media_comment_replies()"]
        REPLY_FETCH --> REPLY_LOOP["Loop: for reply in replies"]
        REPLY_LOOP --> REPLY_MODEL["InstagramComment.from_instagrapi_comment()"]
        REPLY_MODEL --> REPLY_REDIS_CHECK{"cache AND redis.exists?"}
        REPLY_REDIS_CHECK -->|YES| REPLY_SKIP["Skip"]
        REPLY_REDIS_CHECK -->|NO| REPLY_OUTPUT["self.output.put(json)"]
        REPLY_OUTPUT --> REPLY_REDIS_SET["redis.setex(key, 4 hari)"]
        REPLY_SKIP --> REPLY_NEXT["Next reply"]
        REPLY_REDIS_SET --> REPLY_NEXT
    end
```

---

## 7. Profile Crawling Flow

```mermaid
graph TD
    PROFILE_START(["handler(job)"]) --> PROFILE_DISPATCH{"job.type?"}

    PROFILE_DISPATCH -->|get_profile| GET_PROF
    PROFILE_DISPATCH -->|search_profile| SEARCH_PROF

    subgraph getprof ["get_profile"]
        GET_PROF["get_profile()"] --> PROF_LOGIN["logging_in()"]
        PROF_LOGIN --> PROF_INFO["client.user_info_by_username()"]
        PROF_INFO --> PROF_MODEL["InstagramUser.from_instagrapi_user()"]
        PROF_MODEL --> PROF_OUTPUT["self.output.put(json)"]
        PROF_OUTPUT --> PROF_SSDB["store_to_ssdb()"]
    end

    subgraph searchprof ["search_profile"]
        SEARCH_PROF["search_profile()"] --> SEARCH_LOGIN["logging_in()"]
        SEARCH_LOGIN --> SEARCH_USERS["client.search_users(query, count)"]
        SEARCH_USERS --> SEARCH_LOOP["Loop: for user in results"]
        SEARCH_LOOP --> SEARCH_MODEL["InstagramUser.from_instagrapi_user()"]
        SEARCH_MODEL --> SEARCH_OUTPUT["self.output.put(json)"]
        SEARCH_OUTPUT --> SEARCH_SSDB["store_to_ssdb()"]
    end
```

---

## 8. Exception Handling Flow

```mermaid
graph TD
    ERR(["Exception di handler()"]) --> IG_EXC{"InstagramBaseController?"}

    IG_EXC -->|YES| CHECK_CHALLENGE{"challenge pattern?"}
    CHECK_CHALLENGE -->|YES| REPORT_C["report_session()"]
    CHECK_CHALLENGE -->|NO| CHECK_LOGIN{"login_required pattern?"}
    CHECK_LOGIN -->|YES| REPORT_L["report_session()"]

    REPORT_C --> CLASSIFY
    REPORT_L --> CLASSIFY
    CHECK_LOGIN -->|NO| CLASSIFY

    IG_EXC -->|NO| CLASSIFY

    CLASSIFY["MessageException: regex classify"] --> TOO_MANY{"too_many_requests?"}
    TOO_MANY -->|YES| BURY["input.exception_handler(action=bury)"]
    TOO_MANY -->|NO| TIMEOUT{"connection_timeout?"}
    TIMEOUT -->|YES| RELEASE["input.exception_handler(action=release)"]
    TIMEOUT -->|NO| CHALLENGE{"challenge?"}
    CHALLENGE -->|YES| RELEASE
    CHALLENGE -->|NO| LOGIN_REQ{"login_required?"}
    LOGIN_REQ -->|YES| RELEASE
    LOGIN_REQ -->|NO| MEDIA_NA{"media_not_available / 404?"}
    MEDIA_NA -->|YES| DELETE["input.exception_handler(action=delete)"]
    MEDIA_NA -->|NO| DELETE_DEFAULT["input.exception_handler(action=delete)"]
```

---

## 9. Job Chaining Overview

```mermaid
graph LR
    POST_JOB["Post Job - tube: sc_instagram_post"] -->|crawled| POST_OUT["Post Output ke Kafka/NSQ"]

    POST_OUT --> COMMENT_TRIGGER{"comment_count > 0?"}
    COMMENT_TRIGGER -->|YES| COMMENT_JOB["Comment Job - tube: sc_instagram_comment"]

    COMMENT_JOB -->|crawled| COMMENT_OUT["Comment Output ke Kafka/NSQ"]

    COMMENT_OUT --> REPLY_TRIGGER{"reply_count > 0?"}
    REPLY_TRIGGER -->|YES| REPLY_JOB["Reply Job - tube: instagram_replies"]

    REPLY_JOB -->|crawled| REPLY_OUT["Reply Output ke Kafka/NSQ"]

    COMMENT_OUT --> PAGINATION{"has more pages?"}
    PAGINATION -->|YES| COMMENT_JOB
```

---

## 10. Overall System Architecture

```mermaid
graph TD
    subgraph external ["External Dependencies"]
        TOKEN_API["Token Management API - session pool"]
        BEANSTALKD[("Beanstalkd - job queue")]
        REDIS_DB[("Redis - comment cache")]
        SSDB_DB[("SSDB - dedup storage")]
        KAFKA_BROKER[("Kafka / NSQ - output sink")]
        PROXY_API["Proxy Providers - Webshare / Tor"]
    end

    subgraph pod ["Instagram Crawler Pod"]
        CLI["CLI main.py"] --> CONTROLLER["Controller"]
        CONTROLLER --> INSTAGRAPI["instagrapi.Client - device-spoofed + proxy"]
        CONTROLLER --> INPUT_DRV["Input Driver"]
        CONTROLLER --> OUTPUT_DRV["Output Driver"]
    end

    subgraph ig ["Instagram"]
        IG_API["Instagram Private API - i.instagram.com"]
    end

    TOKEN_API -->|"GET/PUT session"| CONTROLLER
    BEANSTALKD -->|reserve job| INPUT_DRV
    INPUT_DRV -->|"delete/bury/release"| BEANSTALKD
    OUTPUT_DRV -->|publish result| KAFKA_BROKER
    CONTROLLER -->|"hexists/hset dedup"| SSDB_DB
    CONTROLLER -->|"get/setex cache"| REDIS_DB
    CONTROLLER -->|"push comment/reply job"| BEANSTALKD
    PROXY_API -->|proxy list| CONTROLLER
    INSTAGRAPI -->|API calls| IG_API
```

---

## 11. Data Model Mapping

```mermaid
graph TD
    subgraph raw ["instagrapi Raw Dict"]
        RAW_POST["media_info / feed item dict"]
        RAW_USER["user_info dict"]
        RAW_COMMENT["comment dict"]
        RAW_HASHTAG["hashtag dict"]
    end

    subgraph mapper ["InstagramMapper"]
        MAP_POST["post_to_model()"]
        MAP_USER["user_to_model()"]
        MAP_COMMENT["comment_to_model()"]
        MAP_HASHTAG["hashtag_to_model()"]
    end

    subgraph models ["Pydantic Models"]
        MODEL_POST["InstagramPost"]
        MODEL_USER["InstagramUser"]
        MODEL_COMMENT["InstagramComment"]
        MODEL_HASHTAG["InstagramHashtag"]
    end

    subgraph transform ["Transformasi Tambahan"]
        DUMP_JSON["model_dump(mode='json')"]
        ENRICH["Tambahkan: type, media_tags, search_metadata, crawling_at"]
    end

    RAW_POST --> MAP_POST --> MODEL_POST
    RAW_USER --> MAP_USER --> MODEL_USER
    RAW_COMMENT --> MAP_COMMENT --> MODEL_COMMENT
    RAW_HASHTAG --> MAP_HASHTAG --> MODEL_HASHTAG

    MODEL_POST --> DUMP_JSON
    MODEL_USER --> DUMP_JSON
    MODEL_COMMENT --> DUMP_JSON

    DUMP_JSON --> ENRICH
    ENRICH --> OUTPUT_JSON["JSON string ke Output Driver"]
```

---

> **Catatan perbedaan README vs kode aktual:**
> - README: config via `.env` → **Kode: `config.ini` via ConfigParser**
> - Beanstalk: pakai library `greenstalk`
> - SSDB: diakses via `redis.StrictRedis` (Redis-protocol compatible)
> - HTML parser (`HtmlParser`) ada tapi tidak dipakai controller Instagram
