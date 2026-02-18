# Tracing additional instructions (e.g. Make my name huge)

**Keep this debug regime in place.** When an additional note does not show in the letter, use tmp debug files to find where it failed.

- **Cover letter service**: `_write_additional_instructions_debug()` writes `tmp/debug_additional_instructions.txt`; `_write_llm_prompt_log` / `_write_llm_response_log` write `llm_prompt_sent.txt` and `llm_response_received.txt`.
- **Docx generator**: `build_docx_from_content()` always writes `tmp/raw-debug.docx` and `tmp/raw-debug-info.txt` after each build.

## 1. tmp/debug_additional_instructions.txt

Written after each docx-only generation. It has:

- **ADDITIONAL_INSTRUCTIONS**: Raw value from the request. If empty, the request did not send it.
- **CONTENT_CONTAINS_STYLE_TAGS**: True if content has [size:], [font:], or [color:]. If False, the LLM did not add styling.
- **CONTENT_PREVIEW**: First 1200 chars of content used for the docx.
- **WHERE IT CAN FAIL**: A) Not in prompt B) LLM ignored C) Pipeline stripped D) No tags in content.

## 2. Other tmp files

- **llm_prompt_sent.txt**: Full prompt. Search for ADDITIONAL INSTRUCTIONS or your note.
- **llm_response_received.txt**: Raw LLM response. Search for your name or [size: or [font:.
- **raw-debug-info.txt**: source, block_count, content preview for docx.

## 3. Interpret

- Section 1 empty -> request did not include additional_instructions.
- Note in prompt but CONTENT_CONTAINS_STYLE_TAGS False -> LLM did not follow.
- CONTENT_CONTAINS_STYLE_TAGS True but docx has no styling -> pipeline stripped or did not apply.

## 4. Copy from Docker

docker cp cc-mobile-api:/app/tmp/. ./tmp-from-docker/
