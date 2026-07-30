# Discussion

This section explains what the results from the Evaluation Results section actually mean, and connects them back to the three research questions from the Proposal.

## A. RQ1 — How can RAG and agentic clarification improve the accuracy and relevance of chatbot responses?

The results show that RAG (Retrieval-Augmented Generation) on its own does not guarantee a correct answer — retrieval and generation are two separate steps, and each can fail in a different way.

Across all three rounds, when a wrong answer was checked, the retrieved knowledge chunk was almost always confirmed to be correct and relevant (verified directly by re-running the retrieval outside the chatbot). The problem was consistently on the **generation** side — the AI model either:
- picked the wrong detail out of a chunk that had more than one fact in it,
- stated the opposite of what the chunk actually said, or
- pulled in an unrelated fact from a different retrieved chunk that wasn't asked about.

This means the accuracy improvement from 56% to 85% was **not** mainly a retrieval-quality improvement. It came from:
- reorganising the knowledge base so each chunk holds one clear fact instead of several combined facts, which reduced how often the model had to pick the "right" detail out of a longer answer, and
- adding rule-based checks after the AI generates its answer, to catch and correct the specific ways it kept going wrong.

Agentic clarification (the chatbot asking a follow-up question when information is missing) also improved over the three rounds. In Round 1, general questions were often wrongly treated as needing a specific order number, so the chatbot asked for details it didn't actually need. By Round 3, this was fixed by teaching the system the difference between "a real action on a specific order" (which genuinely needs an order number) and "a general question about policy" (which doesn't).

**Answer to RQ1:** RAG improves relevance by giving the model real information to work from, but it does not by itself guarantee the response is accurate — the way the model uses that information still needs to be checked and corrected with rule-based logic. Clarification meaningfully reduces wrong answers, but only once the system correctly tells apart a real action request from a general question.

## B. RQ2 — Under what conditions should the chatbot transfer a conversation to human staff?

The evaluation testing surfaced several real examples of both **wrong** and **correct** handover decisions:

| Situation | What should happen | What was found |
|---|---|---|
| Customer explicitly asks for a human | Immediate handover | Worked correctly and consistently |
| A genuinely unanswerable question (e.g. general knowledge, unrelated topic) | Decline politely, offer handover as an option | Worked correctly once the "don't guess" rule was added |
| A general policy question mixed with a negative-sounding word | Should NOT escalate | Initially escalated incorrectly — a neutral question got tagged as a "complaint" and was escalated for no real reason |
| A confidently-answerable question where the retrieval worked | Should NOT escalate | Initially escalated in Round 1 based on sentiment alone, even when the knowledge base already had the answer |

The clearest finding is that handover should be triggered by a **combination of signals**, not any single one. Sentiment alone (e.g. detecting a "negative" or "frustrated" tone) was not reliable enough on its own to decide when to escalate — it needed to be combined with whether an actual complaint intent was also present. Once handover was gated on **both** conditions together, incorrect escalations dropped.

[INSERT IMAGE: Reports/Screenshots/04_human_handover.png — explicit human request handover]

[INSERT IMAGE: Reports/Screenshots/Admin-and-Staff-Dashboards/02_staff_case_with_ai_handover_package.png — staff dashboard showing the handover reason, AI confidence, and full context handed to the staff member]

**Answer to RQ2:** The chatbot should transfer to a human when: (1) the customer explicitly asks, (2) the question is genuinely outside what the system can answer, or (3) a real complaint is detected together with negative sentiment — but not on sentiment alone, and not just because a question mentions a difficult topic in a neutral tone.

## C. RQ3 — How effectively does the proposed prototype meet user expectations for accuracy, handover correctness, usability and feedback?

This question was designed to be answered using two sources: an anonymous questionnaire (~20-30 participants) and a small hands-on usability test (3 participants), as planned in the Proposal.

**Status at time of writing:** [FILL IN — has real questionnaire/usability data been collected by submission time? If yes, insert results/summary here and reference the Google Form responses. If not, state honestly that this data collection was not completed within the project timeframe, and that RQ3 is answered here only from the technical evaluation and a technical walkthrough of the usability tasks, not from real participant feedback.]

What CAN be answered from the technical side:
- All 5 tasks from the usability test script were technically verified to work correctly by walking through them directly (general question, vague question needing clarification, out-of-scope question, explicit human handover) — see evidence below. This confirms the system **functions as intended**, but does not confirm how a real person would **experience** using it (confusion, hesitation, trust) — that requires the actual usability test with real participants.

[INSERT IMAGE: Reports/Screenshots/Usability-Task-Walkthrough/task2_clarification.png — clarification flow working correctly]

[PUT LINK: If real questionnaire data was collected, put the Google Form results/summary link here]

**Answer to RQ3:** Partial. The system meets accuracy and handover-correctness expectations, based on the technical evaluation. Whether it meets *usability and user-trust* expectations cannot be fully answered without real participant data, which is noted as a limitation (see Reflection section).

## D. Answering the Main Research Question

*"How effectively can an agentic AI customer-support chatbot with human handover improve the customer-support experience for JumpStart Retail?"*

Based on the technical evaluation:
- The system reached 85% accuracy on a fixed 26-question test set after three rounds of fixing, up from 56% in the first round.
- Handover logic correctly identifies explicit requests and genuinely unanswerable questions, and was corrected to stop over-escalating on sentiment alone.
- The remaining gaps are (1) a small number of generation-side errors that are inconsistent between runs on the local AI model used, and (2) the lack of real end-user feedback data to confirm the human-experience side of the research question.

So the prototype shows strong evidence of improving accuracy and handover correctness through iterative, evidence-based fixing — but a full answer to "does this improve the customer experience" needs the participant-facing evidence that RQ3 was meant to supply.

## E. Recommendations for JumpStart

Based on what the results actually showed, these are the practical recommendations for JumpStart if this prototype were to move toward real use:

1. **Do not deploy on a small local AI model as-is.** The evaluation showed the small model (chosen here for speed on a normal laptop) is the direct cause of the remaining errors — it does not reliably follow instructions like "don't contradict yourself" or "don't claim you said something you didn't." A larger, more capable model (cloud-hosted or a bigger local model) would likely remove a meaningful share of the remaining 15% error rate.
2. **Keep the rule-based safety checks, don't rely on the AI model's judgement alone.** The single biggest accuracy improvement in this project came from adding fixed code-level rules (e.g. catching self-contradictory answers, correctly routing cancellation requests to a real order lookup), not from better wording of the AI's instructions. Any future version should keep expanding this kind of rule-based safety net rather than assuming a better prompt is enough.
3. **Keep the human handover option visible and easy to reach.** The evaluation confirmed that explicit handover requests worked correctly and reliably every time — this is the one part of the system customers can already depend on, and it should stay a prominent, always-available option even as the automated side improves.
4. **Treat the automated confidence score as a warning signal for staff, not a hard gate.** The admin dashboard's AI Performance and Audit Log pages (see evidence in the Findings section) already show confidence, retrieval quality, and handover reasons per message — this is useful for staff to spot weak answers even when the system doesn't escalate on its own, and should be kept and expanded rather than treated as a fully automated pass/fail signal.
5. **Get real customer feedback before expanding scope.** The technical evaluation shows the system is accurate on the questions it was tested against, but does not confirm whether real customers find it trustworthy or easy to use — before adding more features, JumpStart should prioritise collecting that feedback (see Reflection section).

These recommendations show that the research objectives were **substantially met on the technical side** (accuracy, handover correctness) but that the objective of confirming a genuinely improved *customer experience* still depends on the real user data this project was not able to fully collect in the time available.
