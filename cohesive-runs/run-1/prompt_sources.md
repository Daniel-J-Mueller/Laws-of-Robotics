# Prompt Sources

This run uses actual alignment benchmark prompts from JailbreakBench JBB-Behaviors, not locally invented capability prompts.

- Dataset: `JailbreakBench/JBB-Behaviors`
- Local harmful CSV: `resources_jbb_harmful_behaviors.csv`
- Local benign CSV: `resources_jbb_benign_behaviors.csv`
- Prompt catalog: `prompt_catalog.json`

JBB-Behaviors provides 100 harmful behavior prompts and 100 benign control prompts. Its dataset card describes it as an open robustness benchmark for jailbreaking large language models, with behaviors sourced from prior work including HarmBench and AdvBench and organized into policy categories.

Sources:

- https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors
- https://github.com/JailbreakBench/jailbreakbench
- https://arxiv.org/abs/2404.01318
