# Reflection

This section looks back at the research methods used in this project, how well they worked, and what would be done differently with more time or in future work.

## A. Efficacy of the Research Methods Used

**Manual TP/FP/FN/TN evaluation** was the main method used to measure the chatbot's performance. Looking back, this was the right choice for this project, for a few reasons:

- It caught real, specific bugs that a single overall score would have hidden — for example, it showed exactly which question types were failing and why (wrong routing in Round 1, hallucination in Round 2, self-contradiction in Round 3), not just that "accuracy is 72%."
- It let expected answers be judged on **meaning**, not exact wording — early in the project it was assumed the expected answer text should closely match the chatbot's actual answer, but testing showed the AI always rewords its answers and sometimes combines more than one fact, so grading had to be based on whether the *facts* were correct, not whether the *words* matched.

However, this method also has real weaknesses:

- It is slow. Each round meant manually asking 25-26 questions and reading every response, three separate times.
- On a small local AI model, the exact same question can get a different answer on different runs. This was confirmed directly — testing the same question 3-5 times in a row sometimes gave a correct answer most times and a wrong answer once. A single manual test round can therefore make a bug look "fixed" or "not fixed" just by chance, when it's really a consistency issue with the model itself.

**Deterministic rule-based fixing** (adding fixed logic in the code instead of just changing the AI's instructions) turned out to be the most reliable way to actually fix problems. Every time a fix was attempted only by rewording the prompt/instructions given to the AI, it worked some of the time but not all of the time. Every time a fix was instead written as a hard rule in the code (e.g. "if X pattern is detected, do Y"), it worked consistently. This was an important, repeated lesson across the whole project.

## B. Recommendations

1. **Use a stronger or larger AI model where possible.** The small model used here (chosen for speed, since it runs on a normal laptop) is the direct cause of several remaining issues — it does not follow instructions perfectly every time, especially for subtler things like "don't claim you said something earlier unless you actually did."
2. **Build an automated regression test suite**, not just manual testing. A set of saved questions with expected facts (not exact text) that can be re-run automatically after every code change would catch bugs faster than manually re-testing 26 questions by hand each time.
3. **Collect real user feedback before finalising design decisions.** Some design choices (how the clarification question is worded, how the handover message reads) were based on the researcher's own judgement, not on how real customers actually react to them.
4. **Add a deterministic check for the "as I mentioned earlier" issue**, since it is a known, repeated bug (see Evaluation Results) that the prompt instructions alone do not fully stop.

## C. Limitations of the Study

1. **Small, fixed test set.** 26 questions is enough to catch clear bugs but too small to give a statistically confident accuracy number — a wrong answer on 1 question changes the score by about 4%.
2. **No completed real user research at time of writing.** The questionnaire and usability test were planned and prepared (see the Findings section) [UPDATE THIS LINE based on final actual data collection status], but this project's timeframe made it difficult to reach the originally planned number of real participants.
3. **Model inconsistency.** Because the AI model does not give the same answer every time for the same question, a single test round is not fully reliable — ideally, the same question would be tested multiple times per round to get a more stable result, which was not always done due to time constraints.
4. **Single evaluator.** All manual grading (TP/FP/FN/TN labelling) was done by one person (the researcher), which introduces the possibility of grading bias — a second, independent grader was not available for this project.

## D. Alternative Methodologies Considered

The original Proposal (Methodology Justification section) already considered and rejected using **interviews** as the main primary research method, reasoning that they would need more time for recruitment, transcription, and analysis than the project schedule allowed. Looking back after finishing the technical build, this was still the right call — the technical evaluation alone already consumed most of the available time, so a heavier interview-based method would likely have meant less time available for actually fixing the chatbot.

An alternative not considered in the original Proposal is **automated LLM-as-judge grading** — using a second, larger AI model to automatically read each response and decide TP/FP/FN/TN instead of a human doing it by hand. This could have made repeated re-testing much faster (useful given the model-inconsistency problem above), but it introduces a new question of "how do you know the judge model itself is grading correctly" — trusting one AI to grade another AI's homework has its own reliability problem, and it was outside the scope of what this project could properly validate in the time available.

## E. Future Research Directions

- Repeat the evaluation with a larger, more capable AI model and compare the accuracy trend against the current results, to measure how much of the remaining error is caused by model size specifically.
- Run the questionnaire and usability test with the full originally-planned number of real participants, and compare their feedback against the technical evaluation's findings — do the questions users actually struggle with match the ones the technical testing predicted?
- Investigate a deterministic (not prompt-based) way of tracking what the chatbot has genuinely said earlier in a conversation, to fully close the "as I mentioned" issue.

## F. Concluding Thoughts

The project's central lesson was that a small, locally-run AI model can be made noticeably more reliable — not by asking it more nicely through better prompts, but by wrapping it in deterministic, rule-based checks that catch its specific, repeated mistakes. Manual evaluation was slow, but it was the only way to actually find those specific mistakes in the first place; a single overall accuracy number would never have shown *why* the system was failing, only *that* it was failing.
