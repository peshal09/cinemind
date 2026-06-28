# CineMind — Demo Outputs

Captured artifacts for the README / interviews. All from the real running system
(Postgres + pgvector + Redis; embeddings = `gte-small` over title + genres + overview +
keywords + cast; LLM = Google Gemini 2.5 Flash).

---

## RAG `/ask` — grounded Q&A with citations

The endpoint embeds the question, retrieves the top-k movies from pgvector, and answers
**only** from that context. A groundedness guard skips the LLM for out-of-corpus questions;
citations are validated against the retrieved set (invented titles are dropped).

### 1. Grounded thematic question
**Request:** `POST /ask {"question": "a film about boxing", "k": 5}`
```json
{
  "answer": "The following movies are about boxing: \"Boxer, The (1997)\", \"Fighter, The (2010)\", \"Harder They Fall, The (1956)\", \"Rocky Balboa (2006)\", and \"Champ, The (1979)\".",
  "citations": [
    {"id": 26965, "title": "Boxer, The (1997)"},
    {"id": 81932, "title": "Fighter, The (2010)"},
    {"id": 6064, "title": "Harder They Fall, The (1956)"},
    {"id": 49651, "title": "Rocky Balboa (2006)"},
    {"id": 3428, "title": "Champ, The (1979)"}
  ],
  "used_context": ["Boxer, The (1997)", "Fighter, The (2010)", "Harder They Fall, The (1956)",
                   "Rocky Balboa (2006)", "Champ, The (1979)"]
}
```

### 2. Cast question (uses TMDB top_cast)
**Request:** `POST /ask {"question": "which of these stars Leonardo DiCaprio?", "k": 5}`
```json
{
  "answer": "Leonardo DiCaprio stars in the following movies: The Departed (2006), where he plays an undercover cop infiltrating the Irish Mafia; Celebrity (1998); Gangs of New York (2002), in which he portrays an Irish immigrant seeking revenge; and Shutter Island (2010), where he plays a U.S. Marshal investigating a disappearance.",
  "citations": [
    {"id": 48516, "title": "Departed, The (2006)"},
    {"id": 2356, "title": "Celebrity (1998)"},
    {"id": 5956, "title": "Gangs of New York (2002)"},
    {"id": 74458, "title": "Shutter Island (2010)"}
  ],
  "used_context": ["Departed, The (2006)", "Celebrity (1998)", "Maps to the Stars (2014)",
                   "Gangs of New York (2002)", "Shutter Island (2010)"]
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
> Best retrieval similarity 0.77 < threshold 0.83 → the LLM is never called. With the
> `gte-small` embeddings cosine scores run high and tight — in-domain movie questions land
> ~0.86–0.91, off-topic ones ~0.76–0.81 — so the guard sits at 0.83, cleanly between them.

---

## Semantic search — retrieval by *meaning*, not title words

`POST /search/semantic` embeds the query and ranks movies by cosine similarity. With
`gte-small` the vectors are strong enough that pure semantic search surfaces the right
films even when the query words never appear in the title.

**`"organized crime mafia drama"`**
> The Godfather (1972) · Mobsters (1991) · The Godfather: Part II (1974) · Il Divo (2008) ·
> Jane Austen's Mafia! (1998) · Gomorrah (2008)

**`"a mind-bending sci-fi about dreams"`**
> Akira Kurosawa's Dreams (1990) · Paprika (2006) · In Dreams (1999) · Meshes of the
> Afternoon (1943) · The Science of Sleep (2006) · Inception (2010)

Neither *The Godfather* nor *Inception* / *Paprika* / *Solaris* contains the query words —
they're retrieved on theme. (Upgrading `all-MiniLM-L6-v2` → `gte-small` lifted self-retrieval
hit-rate@10 from 68% to 96%; see below.)

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
| **Retrieval hit-rate@10** (keyword query → own movie in top-10, n=200) | **96%** (192/200) |
| **Groundedness rate** (in-domain questions yielding a grounded, cited answer, n=8) | **100%** (8/8) |

The hit-rate jumped from 68% (all-MiniLM-L6-v2) to 96% after upgrading to `gte-small` and
raising `hnsw.ef_search` to 200 so the ANN index realizes the model's full recall.

Citation matching is tolerant — case-, year-, accent- and article-order-insensitive — with a
prose fallback that recovers titles a model names without the JSON format (e.g. it writes
*"Inception"* and we resolve *Inception (2010)*), so valid citations aren't dropped.
Ungrounded `/ask` answers are still logged (`logger "cinemind.ask"`) for monitoring.
