# Evaluation Results and Analysis

## A. Evaluation Method

To check whether the chatbot's responses were correct, wrong, or wrongly escalated, a fixed test set of 26 questions was used (see `jumpstart_test_set.csv`). Each question was manually run through the live chatbot and the response was labelled using four categories:

- **TP (True Positive)** — the question could be answered, and the chatbot answered it correctly.
- **FP (False Positive)** — the chatbot gave an answer, but the answer was wrong, incomplete in a way that mattered, or contradicted itself.
- **FN (False Negative)** — the question could be answered from the knowledge base, but the chatbot wrongly escalated it to a human or refused to answer.
- **TN (True Negative)** — the question genuinely could not be answered (e.g. "what's the weather today?"), and the chatbot correctly declined or handed it over.

This labelling was done manually across three separate rounds, with fixes applied to the system between each round.

[PUT LINK: Google Form questionnaire link here]
[PUT LINK: Evaluation Excel/CSV files here — jumpstart_evaluation_data.csv, _2.csv, _3.csv]

## B. Evaluation Results

Table I shows how the four values changed across the three evaluation rounds.

**TABLE I. EVALUATION METRICS ACROSS THREE ROUNDS**

| Metric | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| TP | 9 | 17 | 17 |
| FP | 4 | 5 | 3 |
| FN | 7 | 2 | 1 |
| TN | 5 | 1 | 5 |
| Total questions | 25 | 25 | 26 |
| Accuracy | 56% | 72% | 85% |
| Precision | 69% | 77% | 85% |
| Recall | 56% | 89% | 94% |
| F1 Score | 62% | 83% | 89% |

Metric definitions are as follows:

- **Accuracy** = (TP + TN) / Total — how many of all the questions got the correct outcome.
- **Precision** = TP / (TP + FP) — out of all the times the chatbot gave an answer, how many were actually correct.
- **Recall** = TP / (TP + FN) — out of all the questions that could be answered, how many did the chatbot actually answer instead of wrongly escalating.
- **F1 Score** = combines Precision and Recall into one number, so a system can't score well by only being good at one of them.

## C. What Changed Between Each Round

**Round 1 → Round 2:**
- Moved from Groq (cloud LLM) to a local Ollama model, because Groq's daily free quota kept running out during testing.
- Widened the similarity threshold and increased how many knowledge chunks are retrieved per question, because the correct answer was sometimes found but ranked too low to be used.
- Added a rule that stops the chatbot from making up an answer when it has no real information — before this, it would sometimes invent facts (e.g. making up a restaurant name) instead of saying it couldn't help.

**Round 2 → Round 3:**
- Cleaned up the knowledge base — removed rows that repeated the same fact as another row, then split a couple of rows back apart when it turned out the model couldn't reliably pick out the right fact from a very long combined answer.
- Fixed several routing bugs where the chatbot picked the wrong action for a question — for example, treating "I want to cancel my order" the same as a general policy question, instead of realising it needs the customer's real order number.
- Found and fixed a bug where an internal flag (`_force_knowledge`) was silently being dropped between processing steps, which caused some answerable questions to be wrongly escalated.
- Added a check that catches when the chatbot's answer starts by saying "No" to something the knowledge base actually confirms — this was the single biggest fix for accuracy, since it fixed several cases where the chatbot flatly contradicted itself in the same sentence.

## D. Key Findings

- Accuracy improved from 56% to 85% across the three rounds.
- Round 1's biggest problem was **wrong routing** — general questions kept getting treated as if they needed a specific order number.
- Round 2's biggest problem was **hallucination** — the chatbot answering out-of-scope questions with made-up information instead of admitting it didn't know.
- Round 3's biggest problem was **self-contradiction** — the chatbot correctly retrieving the right information, but then stating the opposite of what it retrieved.
- Every fix that actually worked reliably was a **deterministic rule in the code**, not a change to the AI's instructions (the prompt). Telling the model "don't do X" in the prompt was not reliable enough on its own — a smaller/local AI model doesn't follow instructions perfectly every time, so a fixed rule in the code was needed to catch it properly.
- Two issues are still open and not fully fixed:
  1. The chatbot sometimes says "as I mentioned earlier" about something it never actually said before in that conversation.
  2. One specific question (about a stuck order) gives a good answer some of the time and a confused answer other times, even with nothing else changed — this is the AI model itself being inconsistent, not a bug in the code.

## E. Evidence

[INSERT IMAGE: Reports/Screenshots/Admin-and-Staff-Dashboards/04_admin_ai_performance.png — Admin panel showing live Recall@5, Precision@5, and per-intent confidence breakdown]

[INSERT IMAGE: Reports/Screenshots/Admin-and-Staff-Dashboards/06_admin_audit_log_per_message_detail.png — Full per-message audit trail showing detected intent, sentiment, retrieved chunks and similarity scores]
