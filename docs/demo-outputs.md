# CineMind — Demo Outputs

Captured artifacts for the README / interviews. All from the real running system
(Postgres + pgvector + Redis; embeddings = title + genres + overview + keywords + cast;
LLM = Google Gemini Flash).

---

## RAG `/ask` — grounded Q&A with citations

The endpoint embeds the question, retrieves the top-k movies from pgvector, and answers
**only** from that context. A groundedness guard skips the LLM for out-of-corpus questions;
citations are validated against the retrieved set (invented titles are dropped).

### 1. Grounded thematic question
**Request:** `POST /ask {"question": "a mind-bending movie about dreams", "k": 5}`
```json
{
  "answer": "Based on the provided context, there are several movies centered around the theme of dreams. In \"Dreamscape (1984)\", a young man enters the dreams of patients to diagnose their psychic traumas. \"In Dreams (1999)\" features a housewife who has a psychic connection ...",
  "citations": [
    {"id": 2872, "title": "Dreamscape (1984)"},
    {"id": 2752, "title": "In Dreams (1999)"}
  ],
  "used_context": ["Dream Team, The (1989)", "Dreamscape (1984)", "In Dreams (1999)",
                   "Nightmare on Elm Street 3: Dream Warriors, A (1987)",
                   "Nightmare on Elm Street 4: The Dream Master, A (1988)"]
}
```

### 2. Cast question (uses TMDB top_cast)
**Request:** `POST /ask {"question": "which of these stars Leonardo DiCaprio?", "k": 5}`
```json
{
  "answer": "The movie that stars Leonardo DiCaprio is Wolf of Wall Street, The (2013).",
  "citations": [{"id": 106782, "title": "Wolf of Wall Street, The (2013)"}],
  "used_context": ["Three Musketeers, The (2011)", "The Artist (2011)", "Maps to the Stars (2014)",
                   "Wolf of Wall Street, The (2013)", "For Your Consideration (2006)"]
}
```

### 3. Off-topic question — groundedness guard (no LLM call)
**Request:** `POST /ask {"question": "how do I bake sourdough bread?", "k": 5}`
```json
{
  "answer": "I don't have enough info to answer that from the movie database.",
  "citations": [],
  "used_context": []
}
```
> Best retrieval similarity 0.22 < threshold 0.35 → the LLM is never called.
> (A near-topic question like "who won the 2030 election?" *passes* the guard — election
> movies exist at sim ~0.41 — but the LLM then returns a grounded "I don't have that
> information", citing nothing.)

---

## Embedding enrichment — before/after (nearest neighbors to *Inception*)

Adding TMDB overview + keywords to the embedding text dramatically improved semantic
neighbors (cosine distance shown; lower = closer).

| Before (title + genres only) | After (+ overview + keywords) |
|---|---|
| The Crazies (2010) | A Scanner Darkly (2006) |
| Super 8 (2011) | Mission: Impossible – Ghost Protocol (2011) |
| Knowing (2009) | Dreamscape (1984) |
| Iron Man 2 (2010) | Source Code (2011) |
| 2012 (2009) | Trance (2013) |
| Megamind (2010) | Impostor (2002) |

Before = "other 2010 movies"; after = mind-bending sci-fi / heist / dream / subconscious films.

---

## Personalized explanation — `GET /recommendations/{movie_id}/why`

Grounded in the user's **actual rating history** + the movie's attributes (auth-protected).
After the user rated Star Wars, Empire Strikes Back, Terminator 2, and Pulp Fiction 5★:

**Request:** `GET /recommendations/79132/why` (Inception)
```json
{
  "movie_id": 79132,
  "title": "Inception (2010)",
  "why": "If you loved the thrilling action and mind-bending sci-fi elements of *Terminator 2: Judgment Day* and the *Star Wars* films, *Inception* is sure to captivate you with its high-concept dream worlds and intense mission. Additionally, its gripping blend of crime, drama, and thriller genres will appeal to the same sensibilities that made you a fan of *Pulp Fiction*.",
  "based_on": ["Star Wars: Episode IV - A New Hope (1977)",
               "Star Wars: Episode V - The Empire Strikes Back (1980)",
               "Terminator 2: Judgment Day (1991)", "Pulp Fiction (1994)"]
}
```
A new account with no ratings gets a graceful cold-start message instead.

---

## Retrieval quality / RAG groundedness (`python -m app.eval.retrieval`)

| Metric | Value |
|---|---|
| **Retrieval hit-rate@10** (keyword query → own movie in top-10, n=200) | **68%** (136/200) |
| **Groundedness rate** (in-domain questions yielding a grounded, cited answer, n=8) | **100%** (8/8) |

Ungrounded `/ask` answers are logged (`logger "cinemind.ask"`) for monitoring.
