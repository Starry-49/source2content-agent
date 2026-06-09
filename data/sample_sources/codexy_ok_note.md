# Codexy-OK persistent agent workflow

Codexy-OK focuses on making long-running agent work recoverable. The workflow separates stable rules, rolling task state, permission boundaries, verifiers, and handoff notes. A future session should be able to resume from durable state without relying on hidden chat context.

For source-grounded content generation, the same operating principle applies: every run should record its sources, generated artifacts, validation errors, and next-step handoff. If a validation check fails, the system should stop or produce a clearly marked fallback rather than publish unsupported content.

