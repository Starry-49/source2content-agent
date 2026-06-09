# SynQuest source-grounded question workflow

SynQuest turns mixed knowledge sources into a structured question-generation workflow. The source boundary starts with documents such as markdown notes, PDFs, PPTX slides, and README pages. The workflow normalizes these materials into entries, facts, and metadata so later generated content can point back to source ids.

The retrieval layer combines lexical search, TF-IDF style similarity, optional semantic embeddings, and fuzzy matching. The purpose is not to make unsupported claims; it is to locate the most relevant source fragments and then generate drafts that remain traceable to the registered evidence.

Quality rules include duplicate filtering, prompt diversification, source-aware review, and rejection of claims that cannot be linked to a source registry entry.

