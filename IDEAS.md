# Enhancement ideas for subreddit discovery

1. **Time-windowed activity weighting**: adjust scoring to favor recent posts/comments per subreddit (e.g., decay by post age) so trending communities surface faster than long-term but inactive ones.
2. **Cross-subreddit similarity graph**: compute Jaccard/TF-IDF similarity of commenter overlap between candidate subreddits to cluster related communities and boost ones tightly connected to the seed graph.
3. **Content keyword enrichment**: during subreddit and user scans, extract nouns/keywords from titles/selftext to detect thematic matches to the seed keyword or user-selected tags, improving precision for niche topics.
4. **Quality/health signals**: include ratios like upvote-to-comment, removal rates (moderator distinguished comments), and presence of active moderators to penalize spammy or abandoned subreddits.
5. **Temporal growth metrics**: compare subscriber/active_user deltas between cached runs (registry history) to highlight fast-growing subreddits even if absolute numbers are small.
6. **Diversity constraints in results**: enforce category diversity (e.g., limit per parent category or language) to avoid top-N being dominated by a single cluster uncovered via BFS.
7. **Active user sampling heuristics**: for user-based discovery, prioritize prolific commenters/posters (karma per day) and skip near-duplicate low-activity accounts to reduce noise.
8. **External seed expansion**: allow import of seed lists from CSV/JSON and support multi-seed searches (multiple subreddits/users/keywords) merged with weighted aggregation.
9. **Feedback loops**: add UI controls to mark results as relevant/irrelevant, feeding a simple learning-to-rank model (e.g., online logistic regression over current signals) to refine scoring over time.
10. **Fail-open resilience**: when Reddit rate limits or a fetch fails mid-graph, persist partial progress with checkpointing so reruns resume without losing discovered candidates.
