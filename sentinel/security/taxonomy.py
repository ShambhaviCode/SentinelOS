"""Threat taxonomy: the vocabulary SentinelOS uses to explain its decisions."""

TAXONOMY = {
    "PROMPT_INJECTION": {
        "title": "Prompt injection",
        "explanation": "The content tries to override the agent's established instructions "
                       "and redirect it toward an objective the user did not ask for.",
        "why_it_matters": "Agents treat text they read as potential instructions. An injected "
                          "instruction in a document can make an agent act on the attacker's behalf "
                          "using the user's own permissions.",
        "prevented": "The agent did not receive the injected instructions, and any tool request "
                     "made in the same turn was stopped before execution.",
        "recommended_action": "Quarantine the source document, and re-run the task with the "
                              "untrusted content removed or summarized as data only.",
    },
    "DATA_EXPOSURE": {
        "title": "Sensitive data exposure",
        "explanation": "The agent's input contains credentials, secrets or personal identifiers "
                       "that should not leave the local machine or enter an agent's working context.",
        "why_it_matters": "Anything in an agent's context can end up in a tool call, a log or a "
                          "generated response. Secrets in context are one step away from disclosure.",
        "prevented": "The sensitive values were not passed onward, and outbound transmission "
                     "of this content was stopped.",
        "recommended_action": "Remove or rotate the exposed secrets, and give the agent a redacted "
                              "version of the content.",
    },
    "EXCESSIVE_PRIVILEGE": {
        "title": "Excessive privilege",
        "explanation": "The requested access is broader than the stated task needs.",
        "why_it_matters": "Least privilege limits the damage a compromised or confused agent can do. "
                          "Broad file access turns a small mistake into a large exposure.",
        "prevented": "The broad access request was not granted.",
        "recommended_action": "Ask the agent to name the specific file it needs, or grant access "
                              "to a single project folder.",
    },
    "UNSAFE_TOOL_USE": {
        "title": "Unsafe tool use",
        "explanation": "The agent requested a tool action that can change the system or run arbitrary code.",
        "why_it_matters": "Command execution and destructive file operations have effects that cannot "
                          "be undone by reviewing the agent's text output afterwards.",
        "prevented": "The action was held before it could run.",
        "recommended_action": "Review the exact command or operation before approving it.",
    },
    "SUSPICIOUS_DESTINATION": {
        "title": "Suspicious destination",
        "explanation": "The agent wants to send data to a destination that is not on the approved list.",
        "why_it_matters": "Unknown destinations are the most common route for data exfiltration.",
        "prevented": "No data was sent to the destination.",
        "recommended_action": "Confirm the destination is expected, then add it to the network allowlist.",
    },
    "POLICY_VIOLATION": {
        "title": "Policy violation",
        "explanation": "The request breaks a configured SentinelOS policy.",
        "why_it_matters": "Policies encode what this organization has decided agents may do.",
        "prevented": "The request was stopped at the policy boundary.",
        "recommended_action": "Review the policy that triggered, and adjust the request or the policy.",
    },
    "NONE": {
        "title": "No threat detected",
        "explanation": "No known risk patterns were found in the prompt, context or tool request.",
        "why_it_matters": "Low-risk requests pass through without slowing the agent down.",
        "prevented": "Nothing needed to be prevented.",
        "recommended_action": "No action needed.",
    },
}
