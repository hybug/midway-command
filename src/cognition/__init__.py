"""S3 参谋认知与判断系统（s3-staff-cognition-system-plan.md）。

认知链（计划 §一）：
EvidenceView → JudgmentTask → Candidate Hypotheses → evidence_fit
  → ActorProfile + Context + JudgmentDice → chosen_hypothesis
  → error semantics + confidence → JudgmentResult
  → LLM persona rendering → JudgmentMemory

职责边界（计划 §三）：S3 只形成判断与建议；电文收发属 S2、命令执行属 S5、
战斗结算属 S6、参谋关系属 S4。判断建议不直接改变舰队状态（D5）。
"""
