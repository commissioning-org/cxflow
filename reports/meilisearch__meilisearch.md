# Repository research report: meilisearch__meilisearch

Generated: 2025-12-31T21:42:09.967744+00:00

## Snapshot

- Root: `/workspaces/codespaces-blank/.repos/meilisearch__meilisearch`
- Files indexed: 1566
- Total bytes indexed: 12.4 MiB

## Top file extensions

- `(noext)`: 54
- `dump`: 24
- `geojson`: 1
- `gz`: 3
- `json`: 30
- `jsonl`: 2
- `lock`: 1
- `md`: 22
- `mdb`: 6
- `ndjson`: 2
- `png`: 2
- `rs`: 575
- `sh`: 5
- `snap`: 783
- `svg`: 5
- `toml`: 27
- `yml`: 24

## Notable crates / modules (heuristic)

- `crates/meilisearch`
- `crates/milli`
- `crates/index-scheduler`
- `crates/meilitool`
- `crates/openapi-generator`
- `crates/xtask`

## Cargo workspace members (parsed)

- `crates/meilisearch`
- `crates/meilitool`
- `crates/meilisearch-types`
- `crates/meilisearch-auth`
- `crates/meili-snap`
- `crates/index-scheduler`
- `crates/dump`
- `crates/file-store`
- `crates/permissive-json-pointer`
- `crates/milli`
- `crates/filter-parser`
- `crates/flatten-serde-json`
- `crates/json-depth-checker`
- `crates/benchmarks`
- `crates/fuzzers`
- `crates/tracing-trace`
- `crates/xtask`
- `crates/build-info`
- `crates/openapi-generator`

## Environment variables discovered

- `MEILI_APPEND_CONVERSATION_MESSAGE_NAME`
- `MEILI_CONFIG_FILE_PATH`
- `MEILI_DB_PATH`
- `MEILI_DUMP_DIR`
- `MEILI_ENV`
- `MEILI_EXPERIMENTAL_CONFIG_EMBEDDER_FAILURE_MODES`
- `MEILI_EXPERIMENTAL_CONTAINS_FILTER`
- `MEILI_EXPERIMENTAL_DROP_SEARCH_AFTER`
- `MEILI_EXPERIMENTAL_DUMPLESS_UPGRADE`
- `MEILI_EXPERIMENTAL_EMBEDDING_CACHE_ENTRIES`
- `MEILI_EXPERIMENTAL_ENABLE_LOGS_ROUTE`
- `MEILI_EXPERIMENTAL_ENABLE_METRICS`
- `MEILI_EXPERIMENTAL_INDEX_MAX_READERS`
- `MEILI_EXPERIMENTAL_LIMIT_BATCHED_TASKS_TOTAL_SIZE`
- `MEILI_EXPERIMENTAL_LOGS_MODE`
- `MEILI_EXPERIMENTAL_MAX_NUMBER_OF_BATCHED_TASKS`
- `MEILI_EXPERIMENTAL_NB_SEARCHES_PER_CORE`
- `MEILI_EXPERIMENTAL_NO_EDITION_2024_FOR_DUMPS`
- `MEILI_EXPERIMENTAL_NO_EDITION_2024_FOR_FACET_POST_PROCESSING`
- `MEILI_EXPERIMENTAL_NO_EDITION_2024_FOR_PREFIX_POST_PROCESSING`
- `MEILI_EXPERIMENTAL_NO_EDITION_2024_FOR_SETTINGS`
- `MEILI_EXPERIMENTAL_NO_SNAPSHOT_COMPACTION`
- `MEILI_EXPERIMENTAL_PERSONALIZATION_API_KEY`
- `MEILI_EXPERIMENTAL_PROXY_BACKOFF_TIMEOUT_SECONDS`
- `MEILI_EXPERIMENTAL_PROXY_CONNECT_TIMEOUT_SECONDS`
- `MEILI_EXPERIMENTAL_PROXY_REQUEST_TIMEOUT_SECONDS`
- `MEILI_EXPERIMENTAL_REDUCE_INDEXING_MEMORY_USAGE`
- `MEILI_EXPERIMENTAL_REMOTE_SEARCH_TIMEOUT_SECONDS`
- `MEILI_EXPERIMENTAL_REPLICATION_PARAMETERS`
- `MEILI_EXPERIMENTAL_REST_EMBEDDER_MAX_RETRY_DURATION_SECONDS`
- `MEILI_EXPERIMENTAL_REST_EMBEDDER_TIMEOUT_SECONDS`
- `MEILI_EXPERIMENTAL_S3_COMPRESSION_LEVEL`
- `MEILI_EXPERIMENTAL_S3_MAX_IN_FLIGHT_PARTS`
- `MEILI_EXPERIMENTAL_S3_MULTIPART_PART_SIZE`
- `MEILI_EXPERIMENTAL_S3_ROLE_ARN`
- `MEILI_EXPERIMENTAL_S3_SIGNATURE_DURATION_SECONDS`
- `MEILI_EXPERIMENTAL_S3_WEB_IDENTITY_TOKEN_DURATION_SECONDS`
- `MEILI_EXPERIMENTAL_S3_WEB_IDENTITY_TOKEN_FILE`
- `MEILI_EXPERIMENTAL_SEARCH_QUEUE_SIZE`
- `MEILI_HTTP_ADDR`
- `MEILI_HTTP_PAYLOAD_SIZE_LIMIT`
- `MEILI_IGNORE_DUMP_IF_DB_EXISTS`
- `MEILI_IGNORE_MISSING_DUMP`
- `MEILI_IGNORE_MISSING_SNAPSHOT`
- `MEILI_IGNORE_SNAPSHOT_IF_DB_EXISTS`
- `MEILI_IMPORT_DUMP`
- `MEILI_IMPORT_SNAPSHOT`
- `MEILI_LOG_LEVEL`
- `MEILI_MASTER_KEY`
- `MEILI_MAX_INDEXING_MEMORY`
- `MEILI_MAX_INDEXING_THREADS`
- `MEILI_NO_ANALYTICS`
- `MEILI_NO_VERGEN`
- `MEILI_OLLAMA_URL`
- `MEILI_OPENAI_API_KEY`
- `MEILI_S3_ACCESS_KEY`
- `MEILI_S3_BUCKET_NAME`
- `MEILI_S3_BUCKET_REGION`
- `MEILI_S3_BUCKET_URL`
- `MEILI_S3_SECRET_KEY`
- `MEILI_S3_SNAPSHOT_PREFIX`
- `MEILI_SCHEDULE_SNAPSHOT`
- `MEILI_SEARCH_IN_INDEX_FUNCTION_NAME`
- `MEILI_SEARCH_PROGRESS_NAME`
- `MEILI_SEARCH_SOURCES_NAME`
- `MEILI_SERVER_PROVIDER`
- `MEILI_SNAPSHOT_DIR`
- `MEILI_SSL_AUTH_PATH`
- `MEILI_SSL_CERT_PATH`
- `MEILI_SSL_KEY_PATH`
- `MEILI_SSL_OCSP_PATH`
- `MEILI_SSL_REQUIRE_AUTH`
- `MEILI_SSL_RESUMPTION`
- `MEILI_SSL_TICKETS`
- `MEILI_TASK_WEBHOOK_AUTHORIZATION_HEADER`
- `MEILI_TASK_WEBHOOK_URL`
- `MEILI_TEST_FULL_SNAPS`
- `MEILI_TEST_OLLAMA_SERVER`

## README excerpt

Source: `README.md`

> <p align="center">
>   <a href="https://www.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=logo#gh-light-mode-only" target="_blank">
>     <img src="assets/meilisearch-logo-light.svg?sanitize=true#gh-light-mode-only">
>   </a>
>   <a href="https://www.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=logo#gh-dark-mode-only" target="_blank">
>     <img src="assets/meilisearch-logo-dark.svg?sanitize=true#gh-dark-mode-only">
>   </a>
> </p>
> 
> <h4 align="center">
>   <a href="https://www.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">Website</a> |
>   <a href="https://roadmap.meilisearch.com/tabs/1-under-consideration">Roadmap</a> |
>   <a href="https://www.meilisearch.com/pricing?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">Meilisearch Cloud</a> |
>   <a href="https://blog.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">Blog</a> |
>   <a href="https://www.meilisearch.com/docs?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">Documentation</a> |
>   <a href="https://www.meilisearch.com/docs/faq?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">FAQ</a> |
>   <a href="https://discord.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=nav">Discord</a>
> </h4>
> 
> <p align="center">
>   <a href="https://deps.rs/repo/github/meilisearch/meilisearch"><img src="https://deps.rs/repo/github/meilisearch/meilisearch/status.svg" alt="Dependency status"></a>
>   <a href="https://github.com/meilisearch/meilisearch/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-informational" alt="License"></a>
>   <a href="https://github.com/meilisearch/meilisearch/queue"><img alt="Merge Queues enabled" src="https://img.shields.io/badge/Merge_Queues-enabled-%2357cf60?logo=github"></a>
> </p>
> 
> <p align="center">⚡ A lightning-fast search engine that fits effortlessly into your apps, websites, and workflow 🔍</p>
> 
> [Meilisearch](https://www.meilisearch.com?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=intro) helps you shape a delightful search experience in a snap, offering features that work out of the box to speed up your workflow.
> 
> <p align="center" name="demo">
>   <a href="https://where2watch.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demo-gif#gh-light-mode-only" target="_blank">
>     <img src="assets/demo-light.gif#gh-light-mode-only" alt="A bright colored application for finding movies screening near the user">
>   </a>
>   <a href="https://where2watch.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demo-gif#gh-dark-mode-only" target="_blank">
>     <img src="assets/demo-dark.gif#gh-dark-mode-only" alt="A dark colored application for finding movies screening near the user">
>   </a>
> </p>
> 
> ## 🖥 Examples
> 
> - [**Movies**](https://where2watch.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=organization) — An application to help you find streaming platforms to watch movies using [hybrid search](https://www.meilisearch.com/solutions/hybrid-search?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos).
> - [**Flickr**](https://flickr.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=organization) — Search and explore one hundred million Flickr images with semantic search.
> - [**Ecommerce**](https://ecommerce.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos) — Ecommerce website using disjunctive [facets](https://www.meilisearch.com/docs/learn/fine_tuning_results/faceted_search?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos), range and rating filtering, and pagination.
> - [**Songs**](https://music.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos) — Search through 47 million of songs.
> - [**SaaS**](https://saas.meilisearch.com/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos) — Search for contacts, deals, and companies in this [multi-tenant](https://www.meilisearch.com/docs/learn/security/multitenancy_tenant_tokens?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=demos) CRM application.
> 
> See the list of all our example apps in our [demos repository](https://github.com/meilisearch/demos).
> 
> ## ✨ Features
> - **Hybrid search:** Combine the best of both [semantic](https://www.meilisearch.com/docs/learn/experimental/vector_search?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features) & full-text search to get the most relevant results
> - **Search-as-you-type:** Find & display results in less than 50 milliseconds to provide an intuitive experience
> - **[Typo tolerance](https://www.meilisearch.com/docs/learn/relevancy/typo_tolerance_settings?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** get relevant matches even when queries contain typos and misspellings
> - **[Filtering](https://www.meilisearch.com/docs/learn/fine_tuning_results/filtering?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features) and [faceted search](https://www.meilisearch.com/docs/learn/fine_tuning_results/faceted_search?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** enhance your users' search experience with custom filters and build a faceted search interface in a few lines of code
> - **[Sorting](https://www.meilisearch.com/docs/learn/fine_tuning_results/sorting?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** sort results based on price, date, or pretty much anything else your users need
> - **[Synonym support](https://www.meilisearch.com/docs/learn/relevancy/synonyms?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** configure synonyms to include more relevant content in your search results
> - **[Geosearch](https://www.meilisearch.com/docs/learn/fine_tuning_results/geosearch?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** filter and sort documents based on geographic data
> - **[Extensive language support](https://www.meilisearch.com/docs/learn/what_is_meilisearch/language?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** search datasets in any language, with optimized support for Chinese, Japanese, Hebrew, and languages using the Latin alphabet
> - **[Security management](https://www.meilisearch.com/docs/learn/security/master_api_keys?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** control which users can access what data with API keys that allow fine-grained permissions handling
> - **[Multi-Tenancy](https://www.meilisearch.com/docs/learn/security/multitenancy_tenant_tokens?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** personalize search results for any number of application tenants
> - **Highly Customizable:** customize Meilisearch to your specific needs or use our out-of-the-box and hassle-free presets
> - **[RESTful API](https://www.meilisearch.com/docs/reference/api/overview?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=features):** integrate Meilisearch in your technical stack with our plugins and SDKs
> - **AI-ready:** works out of the box with [langchain](https://www.meilisearch.com/with/langchain) and the [model context protocol](https://github.com/meilisearch/meilisearch-mcp)
> - **Easy to install, deploy, and maintain**
> 
> ## 📖 Documentation
> 
> You can consult Meilisearch's documentation at [meilisearch.com/docs](https://www.meilisearch.com/docs/?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=docs).
> 
> ## 🚀 Getting started
> 
> For basic instructions on how to set up Meilisearch, add documents to an index, and search for documents, take a look at our [documentation](https://www.meilisearch.com/docs?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=get-started) guide.
> 
> ## 🌍 Supercharge your Meilisearch experience
> 
> Say goodbye to server deployment and manual updates with [Meilisearch Cloud](https://www.meilisearch.com/cloud?utm_campaign=oss&utm_source=github&utm_medium=meilisearch). Additional features include analytics & monitoring in many regions around the world. No credit card is required.
> 
> ## 🧰 SDKs & integration tools
> 
> Install one of our SDKs in your project for seamless integration between Meilisearch and your favorite language or framework!
> 
> Take a look at the complete [Meilisearch integration list](https://www.meilisearch.com/docs/learn/what_is_meilisearch/sdks?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=sdks-link).
> 
> [![Logos belonging to different languages and frameworks supported by Meilisearch, including React, Ruby on Rails, Go, Rust, and PHP](assets/integrations.png)](https://www.meilisearch.com/docs/learn/what_is_meilisearch/sdks?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=sdks-logos)
> 
> ## ⚙️ Advanced usage
> 
> Experienced users will want to keep our [API Reference](https://www.meilisearch.com/docs/reference/api/overview?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced) close at hand.
> 
> We also offer a wide range of dedicated guides to all Meilisearch features, such as [filtering](https://www.meilisearch.com/docs/learn/fine_tuning_results/filtering?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced), [sorting](https://www.meilisearch.com/docs/learn/fine_tuning_results/sorting?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced), [geosearch](https://www.meilisearch.com/docs/learn/fine_tuning_results/geosearch?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced), [API keys](https://www.meilisearch.com/docs/learn/security/master_api_keys?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced), and [tenant tokens](https://www.meilisearch.com/docs/learn/security/tenant_tokens?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced).
> 
> Finally, for more in-depth information, refer to our articles explaining fundamental Meilisearch concepts such as [documents](https://www.meilisearch.com/docs/learn/core_concepts/documents?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced) and [indexes](https://www.meilisearch.com/docs/learn/core_concepts/indexes?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=advanced).
> 
> ## 🧾 Editions & Licensing
> 
> Meilisearch is available in two editions:
> 
> ### 🧪 Community Edition (CE)
> 
> - Fully open source under the [MIT license](./LICENSE)
> - Core search engine with fast and relevant full-text, semantic or hybrid search
> - Free to use for anyone, including commercial usage
> 
> ### 🏢 Enterprise Edition (EE)
> 
> - Includes advanced features such as:
>   - Sharding
>   - S3-streaming snapshots
> - Governed by a [commercial license](./LICENSE-EE) or the [Business Source License 1.1](https://mariadb.com/bsl11)
> - Not allowed in production without a commercial agreement with Meilisearch.
>   - You may use, modify, and distribute the Licensed Work for non-production purposes only, such as testing, development, or evaluation.
> 
> Want access to Enterprise features? → Contact us at [sales@meilisearch.com](maito:sales@meilisearch.com).
> 
> ## 📊 Telemetry
> 
> Meilisearch collects **anonymized** user data to help us improve our product. You can [deactivate this](https://www.meilisearch.com/docs/learn/what_is_meilisearch/telemetry?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=telemetry#how-to-disable-data-collection) whenever you want.
> 
> To request deletion of collected data, please write to us at [privacy@meilisearch.com](mailto:privacy@meilisearch.com). Remember to include your `Instance UID` in the message, as this helps us quickly find and delete your data.
> 
> If you want to know more about the kind of data we collect and what we use it for, check the [telemetry section](https://www.meilisearch.com/docs/learn/what_is_meilisearch/telemetry?utm_campaign=oss&utm_source=github&utm_medium=meilisearch&utm_content=telemetry#how-to-disable-data-collection) of our documentation.
> [...truncated...]


## Next questions to explore

- Where are HTTP routes defined and wired to handlers?
- Which crate is the indexing/search engine core, and what are its key data structures?
- How does the task scheduler persist state and manage batches?

## Integration notes (this workspace)

We integrated Meilisearch into the FastAPI ML service (`ml/app`) via Meilisearch's REST API (instead of embedding Rust crates).

- New settings in `ml/app/config.py` (env prefix `ML_`): `MEILI_URL`, `MEILI_API_KEY`, `MEILI_MODELS_INDEX`, `MEILI_EXPERIMENTS_INDEX`, etc.
- New stdlib-only client: `ml/app/services/meilisearch.py`
- New indexer: `ml/app/services/search_indexer.py` (builds documents from `MODELS_DIR` metadata + experiments index)
- New API router: `ml/app/api/search.py` wired into `ml/app/main.py`.

Endpoints:

- `GET /search/health`
- `GET /search/models?q=...&filter=...`
- `GET /search/experiments?q=...&filter=...`
- `POST /search/reindex` (supports `dry_run`)
