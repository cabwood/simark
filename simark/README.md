# Retex

## 1. Core Philosophy

* **Author-First Design:** Retex is designed primarily for authors, not programmers. The core goal is clarity, predictability, and ease of use. Complexity should, where possible, be handled by the implementation rather than burdening the author with special rules or non-intuitive behavior. "Just write, it will do what you think it will" is a guiding principle.
* **Literal-First:** Text is the default mode[cite: 262]. Structure, logic, and macros are introduced explicitly via specific syntax.
* **Macro-Native:** Functionality and extensibility are achieved through macros defined and invoked within Retex[cite: 267].
* **Clarity and Control:** Syntax aims for unambiguity[cite: 264]. Evaluation requires explicit invocation (`\`) or reference (`~`), avoiding hidden "magic"[cite: 264, 268].
* **Retex** revisits TeX not to rebuild it — but to rediscover what authorship can be when we start text-first. Inspired by the power of TeX and LaTeX — but designed for authors, not programmers — Retex inverts the traditional paradigm. In Retex, **text is the default**. Logic, macros, and structure appear only where needed, and always in service of the writing. Most tools — TeX, LaTeX, Markdown, even modern programming languages — treat text as a second-class citizen: something to escape, quote, or inject into logic. **Retex flips the script.**, it’s not code with embedded text — it’s **text with embedded logic**. It’s for humans who write, not programs that render.

## 2. Core Concepts

* **Unified Object Model:** Everything represented internally (text, numbers, parameters, defined macros, references, structural groups) is conceptually an `Entity` object[cite: 267, 314].
* **Callability:** All `Entity` objects are callable via the `\` invocation syntax[cite: 315], executing their specific behavior within the current context (e.g., a `Text` entity returns itself[cite: 117], a macro entity executes its body).
* **Evaluation Model:**
    * **`\` (Call):** Triggers *immediate* lookup of `name` and execution of the found entity's `.call()` method[cite: 171, 182]. Call-time arguments (`[A...]`) override definition-time defaults (`[D...]`).
    * **`~` (Reference):** Creates a `Ref(name, args)` object at parse time, representing a *deferred lookup-and-call* (late binding)[cite: 152, 172]. The lookup and execution occur only when the `Ref` object itself is later executed (via `\`).
    * **Immediate RHS Evaluation:** When a binding (`[...]` or `[[...]]`) like `name[D...]=V` is encountered, the RHS expression `V` is evaluated *immediately* at parse time (with the exception of `~` references within it)[cite: 64, 65]. The result of this evaluation is the `Entity` object that gets bound to `name`. This ensures definitions are available for subsequent parsing steps (e.g., for macros involving read-aheads).
* **Scoping Model:**
    * **Local Scope:** Managed by a stack of dictionaries (`Context.local_bindings`)[cite: 1]. Frame 0 is the root local frame. `[...]` modifies the top frame (`[-1]`)[cite: 7].
    * **Global Scope:** Managed by a single, persistent dictionary (`Context.global_bindings[0]`)[cite: 1]. `[[...]]` targets this scope[cite: 8].
    * **Temporary Scopes:**
        * *Macro/Ref Calls:* Push a temporary *local* frame populated by merging definition defaults and call arguments[cite: 75, 76]. Popped on completion.
        * *RHS/Default Evaluation:* To isolate side-effects of bindings encountered during these evaluations, temporary scopes are used. A temporary *local* frame is pushed/popped[cite: 64]. A temporary *global* overlay frame is created/discarded, managed via a capped pseudo-stack (`Context.global_bindings` list max size 2, `global_depth` counter). Global bindings (`[[...]]`) encountered during RHS eval modify this temporary global overlay[cite: 8].
    * **Lookup Order (`get`):** Searches up the local stack (top frame `[-1]` down to root `[0]`), then checks the temporary global overlay (if inside RHS eval), then checks the persistent global frame (`global_bindings[0]`)[cite: 7].

## 3. Syntax and Semantics Summary

* **Text:** Literal text is the default[cite: 262]. Special characters `\`, `~`, `[`, `]`, `{`, `}`, `|`, `` ` `` require escaping with `\` when intended literally[cite: 14].
* **Document Structure:**
    * **Block:** Represents a paragraph or major structural element. Blocks are implicitly separated by one or more blank lines (consumed by `Block.sep_regex` [cite: 38]). A block contains one or more Lines[cite: 38].
    * **Line:** Represents a single line of text ending in a newline character (`\n`)[cite: 39, 131]. A line contains one or more Phrases[cite: 39]. Empty lines (containing no phrases with substance) are skipped[cite: 39].
    * **Phrase:** Represents segments of a line separated by the pipe character (`|`)[cite: 40, 135]. A line with N `|` separators will contain N+1 phrases (empty phrases are permitted, important for table-like structures)[cite: 40, 45]. The `Context.last_phrase_pos` attribute is used by `Phrase.read` to track the end position of the previously read phrase, preventing infinite loops on trailing empty phrases[cite: 44]. A phrase contains one or more Units[cite: 45].
    * **Unit:** The smallest syntactic element (e.g., `Text`, `Ref`, `Call`, `Nest`, `LocalBindings`, `Verbatim`)[cite: 81].
* **Local Binding (`[...]`)**:
    * Syntax: `[name[D...] = V | ...]` (Separator `|`).
    * Action: Evaluates `V` immediately -> `value_entity`. Parses `D` -> `defaults_dict`. Creates `Binding(name, value_entity, defaults_dict, is_local=True)`[cite: 60, 66]. Immediately applies binding via `context.set_local(binding)`[cite: 66, 67]. Bindings within a block are applied sequentially.
    * Scope: Modifies `Context.local_bindings[-1]`[cite: 7].
* **Global Binding (`[[...]]`)**:
    * Syntax: `[[name[D...] = V | ...]]` (Separator `|`).
    * Action: Evaluates `V` immediately -> `value_entity`. Parses `D` -> `defaults_dict`. Creates `Binding(name, value_entity, defaults_dict, is_local=False)`[cite: 60, 66]. Immediately applies binding via `context.set_global(binding)` (targets temporary overlay during RHS eval, else persistent root)[cite: 66, 8]. Bindings within a block are applied sequentially.
    * Scope: Modifies `Context.global_bindings[-1]`[cite: 8].
* **Defaults Definition (`name[D...]` on LHS):**
    * Syntax: `[...]` after name, before `=`, inside a binding block. Contains `key=DefaultValue` pairs separated by `|`. `DefaultValue` evaluated in temporary scope[cite: 62].
    * Semantics: Defines defaults stored *with the binding* (inside the `Binding` object)[cite: 59]. Nested defaults (`key[d]=val`) disallowed[cite: 156].
* **Arguments (`\name[A...]` or `~name[A...]`)**:
    * Syntax: `[...]` immediately following an invocation/reference name. Contains `key=ArgValue` pairs separated by `|`[cite: 68]. `ArgValue` evaluated when parsed.
    * Semantics: Provides named arguments for a specific call. Stored within the `Call` or `Ref` object[cite: 73, 77]. Merged *after* defaults during call setup[cite: 76]. Named-only, optional-only[cite: 395].
* **Invocation (`\name[A...]`)**: Immediate lookup, setup of call frame (defaults+args), execution of bound entity's `.call()`[cite: 78].
* **Reference (`~name[A...]`)**: Creates `Ref(name, A)` object[cite: 74]. Defers lookup and execution until `Ref.call()` is invoked[cite: 75].
* **Structural Grouping (`{...}`)**: Represents a `Nest` entity containing Blocks[cite: 37].
* **Verbatim (``` ``...`` ```):** Literal text content[cite: 30].

## 4. Design Rationale Notes

* Transpiler Compatibility: The Python implementation should strive for compatibility with transpilers (e.g., Transcrypt) to enable potential JavaScript versions for use cases like live web previews. This implies favouring simpler, widely supported Python features and avoiding patterns (such as complex multiple inheritance) where simpler alternatives exist, unless strictly necessary for core functionality.
* **No `@ { ... }` Syntax:** The explicit syntax for anonymous macro definition (`@ { ... }`) was discarded to simplify the surface language for authors. Retex relies on the immediate evaluation of the RHS of bindings (`name=V`) to consistently produce callable `Entity` objects (e.g., `Text`, `Ref`, `Group`). The resulting entity `V` serves as the "macro body". This approach leverages the unified object model and the late-binding reference (`~`) for deferral where needed, aiming for "just write the expression" simplicity.
* **Defaults Stored with Binding:** Default parameter values (`name[D...]=V`) are associated directly with the *binding name* in the namespace registry (implemented by storing a `Binding` object containing name, value, and defaults). This ensures that if the same value entity (`V`) is bound to multiple names (`m1`, `m2`) with different defaults, each name retains its unique defaults, matching the author's intuitive expectation and avoiding silent modification of shared definitions.

## 5. Read-aheads

For authoring simplicity it is possible to write as follows:

`\h Chapter 1 – The Beginning`

This construct will read the text "Chapter 1 – The Beginning" and use that as a content argument for macro `h`. The macro must also be callable with explicit arguments, having the same effect:

`\h[content=Chapter 1 – The Beginning]`

By defining a macro with a default parameter `content=~phrase`, which can be overridden by an explicit argument, both syntaxes are supported:

`[[ h[content=~phrase] = <h1>~content</h1>]]`

Here `phrase` is a macro that reads a single phrase from the current input position.
