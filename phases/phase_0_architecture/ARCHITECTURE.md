## AI Restaurant Recommendation Service – Architecture

This document describes the high-level architecture for an AI-powered restaurant recommendation service (Zomato-style) built with a Next.js frontend and a Python/FastAPI backend. It focuses only on design and structure, not implementation.

- **Frontend**: Next.js (React, HTML/CSS)
- **Backend**: Python + FastAPI
- **Dataset**: `ManikaSaini/zomato-restaurant-recommendation` on Hugging Face
- **LLM Integration**: Conceptual layer only, with Groq as the initial provider accessed via an abstraction layer

---

## 1. System Overview

The system allows users to input their dining preferences (price, location, rating, cuisine, mood, etc.) and returns curated restaurant recommendations. Recommendations are produced by a backend pipeline that:

1. Ingests and preprocesses the Zomato dataset.
2. Filters and scores restaurants based on structured criteria.
3. Optionally leverages an LLM to refine, explain, or personalize the final recommendations.
4. Exposes REST APIs consumed by a Next.js frontend.

The architecture is designed to be:

- **Modular**: Clear separation between data layer, recommendation logic, API layer, frontend, and LLM layer.
- **Incremental**: Built in phases, where each phase is independently buildable, testable, and deployable.
- **Extensible**: Easy to plug in different LLM providers and evolve the recommendation pipeline.

---

## 2. High-Level Architecture & Data Flow

### 2.1 Logical Components

- **Frontend (Next.js)**  
  - User-facing web application for structured preference input and displaying recommendations.  
  - Treats `UserPreference` as the canonical shape for collecting user inputs (location, cuisines, price_range, rating_min, mood), ensuring consistent typing with the backend.

- **Backend API (FastAPI)**  
  - Public REST API for the frontend.  
  - Orchestrates calls to dataset, recommendation pipeline, Mood Interpretation Layer, and LLM interaction layer.  
  - Uses `UserPreference` as the request contract and returns lists of `Recommendation` objects as the response contract.

- **Data Layer**  
  - Dataset ingestion and transformation from Hugging Face.  
  - Local storage (e.g., relational DB or in-memory store) of restaurant metadata, derived features, and indexes.

- **Recommendation Engine**  
  - Deterministic filtering, scoring, and ranking based on preferences.  
  - Optional embeddings-based similarity matching (future enhancement).

- **LLM Interaction Layer (Conceptual)**  
  - Wraps LLM APIs to:  
    - Generate natural language rationales/explanations.  
    - Re-rank or cluster candidate restaurants based on unstructured criteria like “mood”.  
  - Enforces strict input/output schemas to keep the system robust.

### 2.2 End-to-End Data Flow

1. **Dataset Lifecycle (Offline / Background)**  
   - Fetch Zomato dataset from Hugging Face.  
   - Validate schema and types.  
   - Clean and normalize fields (e.g., cuisines, cost for two, rating).  
   - Store processed data in the backend’s data store and build indexes (by city, cuisine, rating, price band).

2. **Request Lifecycle (Online)**  
   - User opens the web app and submits preferences (price, location, rating threshold, cuisine, mood, etc.).  
   - Frontend sends a request to the backend API with structured preference payload.  
   - Backend recommendation engine:  
     - Applies deterministic filters (city, budget, rating threshold, open/closed, etc.).  
     - Scores and ranks filtered restaurants.  
     - Optionally calls the LLM layer with the top-N candidates and the user’s “mood”/context.  
     - LLM returns refined ordering, grouping, and/or explanation text.  
   - Backend returns a structured response: list of recommended restaurants plus optional LLM-generated descriptions.  
   - Frontend renders recommendations and explanations.

---

## 3. Development Phases

Each phase is independently buildable and testable. Later phases build on earlier phases but can be developed, deployed, and validated separately.

### Phase 1 – Dataset Ingestion & Core Data Model

- **Objective**  
  Establish a robust and reproducible pipeline to fetch, validate, and persist the Zomato dataset from Hugging Face, and expose a simple internal data access layer.

- **Key Components**
  - **Dataset Fetcher**  
    - Responsible for downloading the dataset from Hugging Face (offline/one-time or scheduled).  
  - **Schema Validator & Normalizer**  
    - Validates dataset schema (columns, types).  
    - Normalizes key fields (e.g., cuisines list, locations, standardized price ranges, rating buckets).  
  - **Data Storage Layer**  
    - Defines the logical restaurant entity model (e.g., restaurant ID, name, location, cuisines, rating, price band).  
    - Implements basic CRUD-like operations for internal use (e.g., “get restaurants by city”, “get by ID”).
  - **Configuration & Environment Layer**  
    - Configuration for dataset paths, environment variables (e.g., dataset location, DB URL).

- **Inputs**
  - Hugging Face dataset identifier and artifacts.  
  - Configuration parameters (e.g., target city, chosen markets, quality thresholds).

- **Outputs**
  - Cleaned, normalized restaurant records stored in the backend’s data store.  
  - Simple programmatic interface (module) for querying restaurants by basic attributes.

- **Deliverables**
  - Architecture-aligned data model documentation (entities, fields, relationships).  
  - Dataset ingestion script/module with clear entrypoints.  
  - Basic unit tests for schema validation, normalization, and storage operations.  
  - Documentation describing how to run ingestion and what assumptions are made (e.g., supported cities, rating scale).

### Phase 2 – Backend API & Core Recommendation Engine

- **Objective**  
  Provide a production-style FastAPI backend that exposes stable REST endpoints for preferences-based restaurant recommendations using deterministic logic only (no LLM), including a mood-aware scoring layer.

- **Key Components**
  - **API Layer (FastAPI application)**  
    - Route definitions for:  
      - Health checks.  
      - Dataset inspection (e.g., sample restaurants, statistics).  
      - Recommendation endpoint: `/recommendations`.
    - Request/response data models for:  
      - `UserPreference` objects (shared schema used across frontend and backend).  
      - `Recommendation` objects (structured recommendation responses with explanations).
  - **User Preference Schema (Backend View)**  
    - Canonical `UserPreference` model, used at the API boundary and internally, with fields:  
      - `location` (string): city or area identifier corresponding to dataset location fields.  
      - `cuisines` (list of strings): preferred cuisines; empty list means “no strong cuisine preference”.  
      - `price_range` (object or band): either min/max numeric range or a discrete band label (e.g., `low`, `medium`, `high`).  
      - `rating_min` (float): minimum acceptable rating (e.g., 3.5).  
      - `mood` (enum): one of `date_night`, `work_cafe`, `family_dining`, `casual_hangout`, `comfort_food`.  
    - This schema is used consistently in:  
      - Request body validation.  
      - Service layer function signatures (e.g., `generate_recommendations(user_preference: UserPreference)`).  
      - Internal logging and evaluation to ensure preference-driven behavior is traceable.
  - **Mood Interpretation Layer (Deterministic)**  
    - Dedicated component that interprets `UserPreference.mood` into deterministic scoring weights, applied before any LLM involvement.  
    - Maintains a mood-to-weight mapping, for example (conceptually):  
      - `date_night`: high `rating_weight`, high `ambience_weight`, medium `distance_weight`, lower `price_weight`.  
      - `work_cafe`: medium `rating_weight`, high `distance_weight` (short commute), high `ambience_weight` for quiet/comfortable places.  
      - `family_dining`: high `rating_weight`, high `budget/price_weight`, medium `distance_weight`.  
      - `casual_hangout`: balanced `rating_weight` and `distance_weight`, higher weight on popularity/traffic.  
      - `comfort_food`: higher `cuisine_match_weight` and `price_weight`, moderate `rating_weight`.  
    - Produces a **mood-adjusted weight profile** that is fed into the deterministic scoring function (e.g., `rating_weight`, `price_weight`, `ambience_weight`, `distance_weight`, `popularity_weight`), ensuring mood directly affects deterministic scores and is not treated as LLM-only context.
  - **Recommendation Engine (Deterministic)**  
    - Filtering logic:  
      - City/location match.  
      - Budget and rating thresholds.  
      - Cuisine inclusion/exclusion.  
    - Scoring & ranking strategy:  
      - Base weighted scores combining rating, popularity, distance, ambience-related features, and price suitability.  
      - Incorporates the mood-adjusted weight profile from the Mood Interpretation Layer.  
      - Top-N selection with tie-breaking rules.  
  - **Recommendation Response Schema (Backend View)**  
    - Canonical `Recommendation` object returned by the API, including:  
      - `restaurant` (object): core restaurant details (ID, name, cuisines, rating, price band, location, etc.).  
      - `score` (float): final deterministic score after applying mood-adjusted weights.  
      - `matched_factors` (object or list): structured flags/fields capturing why this restaurant was recommended (e.g., `cuisine_match`, `budget_fit`, `high_rating`, `close_by`, `family_friendly`).  
      - `explanation` (string): human-readable explanation of why the restaurant is a good fit. In Phase 2 this is template-based (non-LLM), and in later phases it can be enhanced by LLM output, but it remains a **mandatory** part of the response.  
    - This schema is used consistently across backend modules and propagated to the frontend.
  - **Service Layer / Use Cases**  
    - Use-case-oriented functions such as `generate_recommendations(user_preference)` orchestrating:  
      - Retrieval of candidate restaurants from the data store.  
      - Invocation of the Mood Interpretation Layer.  
      - Deterministic filtering and scoring.  
      - Assembly of `Recommendation` objects with `matched_factors` and `explanation`.

- **Inputs**
  - HTTP requests from frontend or tools carrying `UserPreference` payloads.  
  - Preprocessed dataset (Phase 1 output).

- **Outputs**
  - JSON responses with structured `Recommendation` objects and associated metadata (score, mood-adjusted factors, explanations).

- **Deliverables**
  - FastAPI application structure (routes/controllers, schemas, services modules).  
  - Deterministic, mood-aware recommendation engine module with unit tests.  
  - API documentation (e.g., OpenAPI schema auto-generated by FastAPI, plus higher-level docs) including `UserPreference` and `Recommendation` schemas.  
  - Local testing setup (e.g., API tests using a test client, fixtures for sample dataset).

### Phase 3 – Frontend (Next.js) for Preference Input & Results Display

- **Objective**  
  Build a user-friendly Next.js web application that allows users to enter structured preferences (aligned with the shared `UserPreference` model) and view recommendation results from the backend (structured as `Recommendation` objects).

- **Key Components**
  - **Pages & Routing**
    - Home page with an overview and call to action.  
    - Recommendation page with the main preference form and results display.  
    - Optional about/docs page describing how recommendations are generated.
  - **UI Components**
    - Preference form components, explicitly mapped to `UserPreference` fields:  
      - Mood selector component (dropdown or card-based UI) that allows choosing between `date_night`, `work_cafe`, `family_dining`, `casual_hangout`, `comfort_food`.  
      - Dropdown for all available locations (aligned with dataset locations and backend expectations).  
      - Cuisine multi-select.  
      - Price range slider or band selector.  
      - Rating threshold selector.  
    - Results list:  
      - Restaurant cards showing name, rating, price band, cuisine, address, and badges (e.g., “Top Rated”).  
      - Explanation panel or inline explanation section that displays the `explanation` text from each `Recommendation`, alongside key `matched_factors` (e.g., badges or chips for “Within budget”, “Matches your cuisine”, “Great for families”).  
      - Sorting/filtering controls (e.g., sort by rating or price).
  - **Frontend Service Layer**
    - HTTP client wrappers for calling backend APIs.  
    - Serialization/deserialization logic that uses the shared `UserPreference` shape for requests and `Recommendation` shape for responses, ensuring strict alignment with backend schemas.
  - **State Management**
    - Local component state or lightweight global state to store `UserPreference` objects and current `Recommendation` lists.

- **Inputs**
  - User interactions with web UI (form inputs, clicks) that build or update a `UserPreference` instance.  
  - Responses from backend recommendation APIs containing arrays of `Recommendation` objects.

- **Outputs**
  - Rendered UI showing restaurant recommendations, explanations, and matched factors.  
  - Client-side analytics events or logs (optional, e.g., which moods or locations are most used).

- **Deliverables**
  - Next.js project-level architectural decisions (pages vs app router, layout structure).  
  - Implemented pages and reusable components matching the design, including the mood selector and explanation panel.  
  - Integration tests or manual test scripts for end-to-end flows (frontend → backend → frontend).  
  - UX documentation or mockups showing intended user journeys, especially how mood selection and explanations are presented.

### Phase 4 – Advanced Recommendation Features (Non-LLM)

- **Objective**  
  Enhance recommendation quality and flexibility using advanced but still deterministic techniques, preparing for LLM integration while remaining testable and explainable.

- **Key Components**
  - **Feature Engineering Layer**
    - Derived attributes:  
      - Cuisine categories (e.g., grouping similar cuisines).  
      - Affordability index based on cost vs user budget.  
      - Popularity/traffic indicators inferred from dataset fields.  
    - Encapsulation of feature calculation logic separate from data ingestion and core scoring.
  - **Personalization Rules (Non-LLM)**
    - Simple user profiles (session-based or stateless) that influence scoring, such as:  
      - Historic preference patterns (e.g., often chooses spicy food).  
      - Hard constraints vs soft preferences.
  - **Explainability Layer (Deterministic)**
    - Machine-readable reason codes (e.g., “matched preferred cuisine”, “within budget”, “high rating”).  
    - Short textual summaries generated from templates (not LLM).

- **Inputs**
  - User preferences and potentially simple profile information.  
  - Existing dataset enriched with new derived features.

- **Outputs**
  - Improved ranking of restaurants with richer metadata and reason codes.  
  - Data structures ready to be passed to LLM layer in the next phase.

- **Deliverables**
  - Feature engineering module documentation and tests.  
  - Updated recommendation engine that incorporates new features and rules.  
  - Updated API contract (if needed) to expose reason codes and additional fields.  
  - Performance and quality evaluation artifacts (e.g., offline metrics or curated test cases).

### Phase 5 – LLM Interaction Layer (Conceptual Integration)

- **Objective**  
  Introduce a conceptual LLM-backed layer, built on top of Groq as the initial LLM provider, that refines recommendations and generates natural language explanations, while preserving deterministic core logic as the source of truth.

- **Key Components**
  - **LLM Client Abstraction (Conceptual, Groq-Backed)**
    - Logical interface for:  
      - Sending structured prompt payloads (user preferences + top-N candidate restaurants + reason codes and `matched_factors`).  
      - Receiving structured outputs (e.g., enhanced ordering, groupings, textual explanations).
    - Implemented conceptually as an `LLMProvider` abstraction with Groq as the default concrete provider, while keeping the design open for other providers if needed later.
  - **Prompt Orchestration (Conceptual)**
    - Definition of information that will be sent to the LLM, including:  
      - User’s mood and qualitative preferences (as captured in `UserPreference.mood` and other fields).  
      - Deterministic scores, matched factors, and template-based explanations computed in earlier phases.  
    - Target output schema:  
      - Possibly re-ranked list, restaurant clusters (e.g., “Best for date night”), and enriched human-readable explanations used to populate the `explanation` field in each `Recommendation`.
  - **Safety & Guardrails (Conceptual)**
    - Clear boundaries:  
      - LLM (via Groq) cannot create restaurants that don’t exist in the dataset.  
      - LLM output is validated against the candidate set and `Recommendation` schema.  
    - Fallback strategies when Groq or the LLM layer is unavailable or output is invalid (e.g., revert to deterministic ranking and template-based explanations).
  - **Integration with Recommendation Engine**
    - Recommendation engine provides a candidate set and metadata (`Recommendation` objects) to the LLM layer.  
    - LLM layer returns refined recommendation artifacts (e.g., updated explanation narratives, optional re-ranking) which are then served to the frontend without violating deterministic constraints.

- **Inputs**
  - Candidate restaurants and metadata from deterministic engine, represented as `Recommendation` objects.  
  - User preferences, including mood and contextual hints, represented as `UserPreference`.  
  - Configuration indicating whether LLM mode (Groq-backed) is enabled.

- **Outputs**
  - Enhanced, human-centric recommendation payloads that may include:  
    - Re-ranked list.  
    - Thematic groupings.  
    - Narrative explanations for each recommendation set or individual restaurant, populating or enriching the `explanation` field.

- **Deliverables**
  - Conceptual interface definitions and contracts (no concrete implementation).  
  - Documentation describing Groq integration assumptions, prompt structure, expected LLM outputs, validation rules, and failure handling strategies.  
  - Updated API/response schemas to explicitly account for LLM-enriched explanations while keeping `explanation` mandatory.

### Phase 6 – Observability, Evaluation, and Operational Concerns

- **Objective**  
  Make the system observable, measurable, and production-ready from an architectural perspective.

- **Key Components**
  - **Logging & Monitoring (Conceptual)**
    - Standard logging strategy across backend modules.  
    - Metrics for: request volume, latency, error rates, recommendation success indicators.  
  - **Evaluation Framework**
    - Offline evaluation datasets and scenarios to compare different recommendation strategies (pure deterministic vs LLM-augmented).  
    - Hooks for A/B testing in frontend (conceptual).
  - **Configuration & Feature Flags**
    - Ability to toggle advanced features and LLM layer.  
    - Environment-specific configuration (local, staging, production).

- **Inputs**
  - Application telemetry, configuration toggles, evaluation scenarios.

- **Outputs**
  - Metrics and logs for system behavior.  
  - Evaluation reports to guide further tuning and feature development.

- **Deliverables**
  - Observability and monitoring plan.  
  - Evaluation strategy documentation.  
  - Configuration and feature flagging guidelines.

---

## 4. Backend Modules (Conceptual Structure)

Below is a conceptual breakdown of backend modules. These are logical components; actual file/folder layout will be decided during implementation.

- **Config Module**
  - Handles environment variables, dataset paths, and feature flags.

- **Data Ingestion Module**
  - Dataset fetching from Hugging Face.  
  - Schema validation and normalization logic.  
  - Data-loading routines to populate the storage layer.

- **Storage/Repository Module**
  - Restaurant entity definitions at the conceptual level.  
  - Query functions for retrieving restaurants by different criteria.

- **Feature Engineering Module**
  - Derivation of advanced features for scoring and filtering.

- **Recommendation Engine Module**
  - Deterministic filtering, mood-aware scoring, and ranking functions.  
  - Orchestration logic that combines data access, Mood Interpretation Layer outputs, feature engineering, and business rules.

- **LLM Interaction Module (Conceptual)**
  - Abstract client interface and orchestration functions for Groq-backed LLM calls (with a pluggable provider abstraction).  
  - Validation and guardrails around LLM input/output, including strict adherence to `Recommendation` schemas and candidate sets.

- **API Module (FastAPI Application)**
  - Route handlers for recommendations, health checks, dataset info.  
  - Request/response model definitions.  
  - Dependency wiring connecting routes to services and engines.

- **Testing & Evaluation Module**
  - Test utilities, fixtures, and evaluation scripts for offline experiments.

---

## 5. Frontend Modules (Conceptual Structure)

These represent logical areas of responsibility within the Next.js application.

- **Routing & Pages**
  - Home, recommendations, about/help.

- **UI Components**
  - Layout (header, footer, navigation).  
  - Form components for capturing user preferences, structured around the shared `UserPreference` model:  
    - Mood selector component (e.g., dropdown or card-based UI) using the fixed enum options: `date_night`, `work_cafe`, `family_dining`, `casual_hangout`, `comfort_food`.  
    - Dropdown for all available locations (populated from backend or static config aligned with dataset).  
    - Cuisine multi-select.  
    - Price range selector (slider or band-based control).  
    - Rating threshold selector.  
  - Result cards and lists for displaying restaurants, including an **explanation panel** or inline explanation area that surfaces the `explanation` field from each `Recommendation` (deterministic or LLM-enhanced).

- **Frontend Services**
  - API client for calling backend endpoints using the shared `UserPreference` schema for requests and `Recommendation` schema for responses.  
  - Error and loading state handling.

- **State & Hooks**
  - Custom hooks for managing `UserPreference` state and lists of `Recommendation` objects.  
  - Optional context for global app state.

- **Styling & Design System**
  - Reusable style primitives (colors, typography, spacing).  
  - Theming choices for a restaurant-discovery experience.

- **Analytics (Conceptual)**
  - Capture key user interactions to inform future improvements (e.g., which recommendations get clicked).

---

## 6. Dataset Handling Strategy

- **Source of Truth**
  - Use the Hugging Face dataset as the primary source of restaurant data, but never query it directly at request time; instead, ingest and preprocess into an internal store.

- **Ingestion Frequency**
  - Initial manual ingestion, with an architectural option for scheduled re-ingestion or updates.

- **Data Quality & Validation**
  - Enforce consistent types and value ranges (e.g., rating 0–5, price bands).  
  - Deduplicate records and handle missing values (e.g., default values, exclusion rules).

- **Indexing & Performance**
  - Design indexes around typical query patterns (by city, cuisine, rating, price).  
  - Prepare for potential scaling to larger datasets (e.g., sharding strategies, caching concepts).

- **Dataset Versioning & Reproducibility**
  - Track dataset version or snapshot IDs in configuration.  
  - Maintain documentation on which dataset version is used in which environment.

---

## 7. Recommendation Pipeline Summary

Conceptually, the recommendation pipeline consists of:

1. **Preprocessing (Offline)**  
   - Ingest dataset, clean and normalize, compute derived features.
2. **Candidate Generation (Online)**  
   - Filter restaurants by hard constraints (location, price, rating, dietary/cuisine).  
3. **Scoring & Ranking (Online)**  
   - Apply a scoring function based on user preferences and derived features; select top-N.  
4. **Enrichment & Explainability (Online)**  
   - Attach reason codes and simple template-based explanations.  
5. **LLM Augmentation (Optional, Online)**  
   - Send candidates and context to LLM; receive refined orderings and natural language narratives.  
6. **Response Assembly (Online)**  
   - Build a structured JSON response consumed by the frontend.

Each stage is modular and testable in isolation (e.g., unit tests for scoring, integration tests for pipeline).

---

## 8. LLM Interaction Layer (Conceptual Only)

- **Role in the System**
  - Adds a human-centric layer on top of deterministic recommendations to:  
    - Interpret nuanced or qualitative preferences (“chill vibe”, “date night”, “family-friendly”).  
    - Provide narrative explanations and grouping of results.  
    - Potentially perform light re-ranking within a bounded candidate set.

- **Design Principles**
  - **Separation of Concerns**:  
    - Deterministic engine remains the primary authority over which restaurants are valid candidates.  
    - LLM layer can influence ordering and presentation, but never invents new entities.
  - **Contract-Driven**:  
    - Clearly defined request/response schema for LLM calls.  
    - Strong validation and robust error handling.  
  - **Pluggable Provider**:  
    - Encapsulate all provider-specific details in a single conceptual client.  
    - Enable swapping between different LLM backends without impacting business logic.

- **Failure Modes & Fallbacks**
  - If LLM is disabled or fails:  
    - Serve deterministic recommendations only.  
    - Optionally use template-based explanations.  
  - If LLM output is invalid:  
    - Validate output against candidate list and schema; on failure, discard or sanitize.

---

## 9. Phase Independence & Testability

Each phase is intentionally isolated and testable:

- **Phase 1** can be run and validated without any API or UI, using unit tests and inspection of the stored dataset.  
- **Phase 2** can use synthetic or small sample datasets and expose its API for testing via HTTP clients.  
- **Phase 3** can mock or stub backend APIs for frontend development and UX validation.  
- **Phase 4** can be evaluated offline by comparing recommendation quality before/after feature engineering.  
- **Phase 5** can be prototyped and validated in a sandbox environment with mocked LLM responses.  
- **Phase 6** operates across all phases but can be gradually adopted (e.g., start with logging, then add metrics and evaluation).

This architecture ensures the system can evolve from a simple deterministic recommender to an LLM-augmented experience while remaining maintainable, explainable, and testable at every step.

