(() => {
  "use strict";

  const els = {
    apiBase: document.getElementById("api-base"),
    message: document.getElementById("message"),
    checkReady: document.getElementById("check-ready"),
    ask: document.getElementById("ask"),
    replay: document.getElementById("replay"),
    readyStatus: document.getElementById("ready-status"),
    readyRevision: document.getElementById("ready-revision"),
    requestStatus: document.getElementById("request-status"),
    replayStatus: document.getElementById("replay-status"),
    result: document.getElementById("result"),
    resultBadge: document.getElementById("result-badge"),
    answer: document.getElementById("answer"),
    revision: document.getElementById("revision"),
    entitiesBlock: document.getElementById("entities-block"),
    entities: document.getElementById("entities"),
    relationshipsBlock: document.getElementById("relationships-block"),
    relationships: document.getElementById("relationships"),
    evidenceBlock: document.getElementById("evidence-block"),
    evidenceCount: document.getElementById("evidence-count"),
    evidence: document.getElementById("evidence"),
    emptyGrounding: document.getElementById("empty-grounding"),
    suggestedActions: document.getElementById("suggested-actions"),
    actionsList: document.getElementById("actions-list"),
    error: document.getElementById("error"),
    errorStatus: document.getElementById("error-status"),
    errorCode: document.getElementById("error-code"),
    errorMessage: document.getElementById("error-message"),
    errorDetails: document.getElementById("error-details"),
    coverageDetail: document.getElementById("coverage-detail"),
    unknownProjections: document.getElementById("unknown-projections"),
    rawJson: document.getElementById("raw-json"),
    history: document.getElementById("history"),
    historySummary: document.getElementById("history-summary"),
  };

  // replayRecord is captured at submission time (before fetch):
  //   submittedPayload, submittedApiBase, responseBaseline | null
  // historyBody is separate: last successful display for stale history only.
  const state = {
    template: null,
    ready: false,
    inFlight: false,
    replayRecord: null,
    historyBody: null,
  };

  function setText(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function clearChildren(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function appendTextItem(list, text) {
    const li = document.createElement("li");
    li.textContent = text;
    list.appendChild(li);
  }

  function apiBase() {
    return els.apiBase.value.replace(/\/+$/, "");
  }

  // PostgreSQL JSONB replay can reorder object keys while preserving semantics.
  // Compare canonical forms so Exact replay matched reflects value equality.
  function canonicalize(value) {
    if (Array.isArray(value)) {
      return value.map(canonicalize);
    }
    if (value && typeof value === "object") {
      const out = {};
      for (const key of Object.keys(value).sort()) {
        out[key] = canonicalize(value[key]);
      }
      return out;
    }
    return value;
  }

  function responsesEqual(left, right) {
    return JSON.stringify(canonicalize(left)) === JSON.stringify(canonicalize(right));
  }

  function newRequestId() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
      return `req:browser-${globalThis.crypto.randomUUID()}`;
    }
    return `req:browser-${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
  }

  function setReadyUi() {
    const canAsk = Boolean(state.template) && state.ready && !state.inFlight;
    els.ask.disabled = !canAsk;
    els.replay.disabled = !(state.replayRecord && !state.inFlight);
  }

  function markResultStale(reason) {
    if (!state.historyBody) {
      els.history.classList.add("hidden");
      return;
    }
    const answer = state.historyBody.answer || "";
    const revision = state.historyBody.revision_id || "";
    setText(
      els.historySummary,
      `${reason} Prior answer retained as history only: ${answer} (${revision})`,
    );
    els.history.classList.remove("hidden");
  }

  function hideCurrentViews() {
    els.result.classList.add("hidden");
    els.error.classList.add("hidden");
    setText(els.replayStatus, "");
  }

  function beginRequest(label) {
    state.inFlight = true;
    setReadyUi();
    hideCurrentViews();
    markResultStale(label);
    els.result.classList.add("hidden");
    setText(els.requestStatus, label);
    els.requestStatus.className = "status pending";
  }

  function endRequest() {
    state.inFlight = false;
    setReadyUi();
  }

  function renderError({ httpStatus, code, message, details, network }) {
    els.result.classList.add("hidden");
    els.error.classList.remove("hidden");
    if (network) {
      setText(els.errorStatus, "Network unavailable — no HTTP response.");
      setText(els.errorCode, "");
      setText(els.errorMessage, message || "The API host could not be reached.");
      setText(els.errorDetails, "");
    } else {
      setText(
        els.errorStatus,
        httpStatus == null ? "Request failed." : `HTTP ${httpStatus}`,
      );
      setText(els.errorCode, code ? `code: ${code}` : "");
      setText(els.errorMessage, message || "Sanitized error response.");
      setText(
        els.errorDetails,
        details == null ? "" : JSON.stringify(details, null, 2),
      );
    }
    setText(els.requestStatus, "Failed.");
    els.requestStatus.className = "status error";
  }

  function projectionsByKind(body) {
    const known = {
      entity_brief: [],
      relationship_list: [],
      evidence_summary: [],
    };
    const unknown = [];
    const projections = Array.isArray(body.semantic_projections)
      ? body.semantic_projections
      : [];
    for (const projection of projections) {
      const kind = projection && projection.kind;
      if (kind && Object.prototype.hasOwnProperty.call(known, kind)) {
        known[kind].push(projection);
      } else {
        unknown.push(projection);
      }
    }
    return { known, unknown };
  }

  function renderSuccess(body, { replayMatched, ambiguousRetry }) {
    els.error.classList.add("hidden");
    els.result.classList.remove("hidden");
    els.history.classList.add("hidden");

    setText(els.answer, body.answer || "");
    setText(
      els.revision,
      body.revision_id ? `revision_id: ${body.revision_id}` : "revision_id: (missing)",
    );

    const { known, unknown } = projectionsByKind(body);
    clearChildren(els.entities);
    clearChildren(els.relationships);
    clearChildren(els.evidence);
    clearChildren(els.actionsList);

    for (const projection of known.entity_brief) {
      const payload = projection.payload || {};
      const parts = [
        payload.label || "(unlabeled)",
        payload.kind ? `[${payload.kind}]` : null,
        payload.object_id || null,
      ].filter(Boolean);
      let line = parts.join(" ");
      if (Array.isArray(payload.aliases) && payload.aliases.length) {
        line += ` · aliases: ${payload.aliases.join(", ")}`;
      }
      if (payload.summary) {
        line += ` · ${payload.summary}`;
      }
      appendTextItem(els.entities, line);
    }

    const relationshipRows = [];
    for (const projection of known.relationship_list) {
      const rows = (projection.payload && projection.payload.relationships) || [];
      for (const row of rows) {
        relationshipRows.push(
          `${row.subject_object_id || "?"} — ${row.predicate || "?"} → ${
            row.object_object_id || "?"
          }`,
        );
      }
    }
    for (const line of relationshipRows) {
      appendTextItem(els.relationships, line);
    }

    const evidenceIds = [];
    for (const projection of known.evidence_summary) {
      const ids = (projection.payload && projection.payload.evidence_ref_ids) || [];
      for (const id of ids) {
        evidenceIds.push(id);
      }
    }
    setText(
      els.evidenceCount,
      evidenceIds.length ? `admitted evidence: ${evidenceIds.length}` : "",
    );
    for (const id of evidenceIds) {
      appendTextItem(els.evidence, id);
    }

    const hasEntities = known.entity_brief.length > 0;
    const hasRelationships = relationshipRows.length > 0;
    const hasEvidence = evidenceIds.length > 0;
    els.entitiesBlock.classList.toggle("hidden", !hasEntities);
    els.relationshipsBlock.classList.toggle("hidden", !hasRelationships);
    els.evidenceBlock.classList.toggle("hidden", !hasEvidence);
    els.emptyGrounding.classList.toggle(
      "hidden",
      hasEntities || hasRelationships || hasEvidence,
    );

    const actions = Array.isArray(body.suggested_actions) ? body.suggested_actions : [];
    if (actions.length) {
      els.suggestedActions.classList.remove("hidden");
      for (const action of actions) {
        const kind = action && action.kind ? action.kind : "unknown";
        appendTextItem(
          els.actionsList,
          `${kind}: unavailable in this read-only consumer (not implemented here)`,
        );
      }
    } else {
      els.suggestedActions.classList.add("hidden");
    }

    if (hasEntities || hasRelationships || hasEvidence) {
      setText(
        els.resultBadge,
        replayMatched ? "Grounded · exact replay" : "Grounded",
      );
      els.resultBadge.className = replayMatched ? "badge replay" : "badge";
    } else {
      setText(
        els.resultBadge,
        replayMatched ? "Abstention · exact replay" : "Abstention",
      );
      els.resultBadge.className = "badge abstain";
    }

    setText(
      els.coverageDetail,
      JSON.stringify(
        {
          coverage: body.coverage || null,
          diagnostics: body.diagnostics || [],
        },
        null,
        2,
      ),
    );
    setText(
      els.unknownProjections,
      unknown.length ? JSON.stringify(unknown, null, 2) : "(none)",
    );
    setText(els.rawJson, JSON.stringify(body, null, 2));

    if (replayMatched) {
      setText(els.requestStatus, "Exact replay matched.");
      setText(els.replayStatus, "Exact replay matched");
    } else if (ambiguousRetry) {
      setText(
        els.requestStatus,
        "Exact submitted request was retried.",
      );
      setText(
        els.replayStatus,
        "Exact submitted request was retried (no prior response to compare).",
      );
    } else {
      setText(els.requestStatus, "Mind Turn response received.");
      setText(els.replayStatus, "");
    }
    els.requestStatus.className = "status ok";
  }

  async function loadTemplate() {
    const response = await fetch("./demo-request.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`demo-request.json failed (${response.status})`);
    }
    state.template = await response.json();
    if (!els.message.value && state.template.message) {
      els.message.value = state.template.message;
    }
  }

  async function checkReadiness() {
    state.inFlight = true;
    setReadyUi();
    setText(els.requestStatus, "Checking readiness…");
    els.requestStatus.className = "status pending";
    try {
      const response = await fetch(`${apiBase()}/readyz`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      let body = null;
      try {
        body = await response.json();
      } catch (_err) {
        body = null;
      }
      if (!response.ok) {
        state.ready = false;
        setText(
          els.readyStatus,
          `Not ready (HTTP ${response.status}). Ask remains disabled.`,
        );
        els.readyStatus.className = "status error";
        setText(
          els.readyRevision,
          body && body.error
            ? `${body.error.code || "error"}: ${body.error.message || ""}`
            : "",
        );
        markResultStale("Readiness failed.");
        hideCurrentViews();
        renderError({
          httpStatus: response.status,
          code: body && body.error && body.error.code,
          message: body && body.error && body.error.message,
          details: body && body.error && body.error.details,
        });
        return;
      }
      state.ready = body && body.status === "ready";
      if (state.ready) {
        setText(els.readyStatus, "API ready.");
        els.readyStatus.className = "status ready";
        setText(
          els.readyRevision,
          body.revision_id
            ? `host reports revision_id: ${body.revision_id}`
            : "host ready; revision not reported",
        );
        els.error.classList.add("hidden");
        setText(els.errorStatus, "");
        setText(els.errorCode, "");
        setText(els.errorMessage, "");
        setText(els.errorDetails, "");
        setText(els.requestStatus, "Ready for Ask.");
        els.requestStatus.className = "status ok";
      } else {
        setText(els.readyStatus, "Readiness payload was not ready.");
        els.readyStatus.className = "status error";
        setText(els.readyRevision, JSON.stringify(body || {}, null, 2));
      }
    } catch (_err) {
      state.ready = false;
      setText(els.readyStatus, "API unavailable.");
      els.readyStatus.className = "status error";
      setText(els.readyRevision, "");
      markResultStale("API unavailable.");
      hideCurrentViews();
      renderError({
        network: true,
        message: "Could not reach /readyz. Confirm the API host and CORS origin.",
      });
    } finally {
      endRequest();
    }
  }

  function buildAskPayload() {
    if (!state.template) {
      throw new Error("request template not loaded");
    }
    // Clone the canonical template; replace only request_id and message.
    const payload = JSON.parse(JSON.stringify(state.template));
    payload.request_id = newRequestId();
    payload.message = els.message.value;
    return payload;
  }

  async function postMindTurn(payload, submittedApiBase, { isReplay }) {
    // Capture the replay record at submission time — before fetch — so a lost
    // response still leaves Replay able to resend the exact request to the
    // exact host. New Ask replaces any prior record (including after success A
    // then failed B). Replay keeps the existing record and its baseline.
    if (!isReplay) {
      state.replayRecord = {
        submittedPayload: payload,
        submittedApiBase: submittedApiBase,
        responseBaseline: null,
      };
    }

    beginRequest(
      isReplay ? "Replaying exact request…" : "Submitting Mind Turn…",
    );
    try {
      const response = await fetch(`${submittedApiBase}/v1/mind-turn`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      let body = null;
      try {
        body = await response.json();
      } catch (_err) {
        body = null;
      }
      if (!response.ok) {
        // Record already retained; do not restore a prior successful payload.
        renderError({
          httpStatus: response.status,
          code: body && body.error && body.error.code,
          message: body && body.error && body.error.message,
          details: body && body.error && body.error.details,
        });
        return;
      }

      let replayMatched = false;
      let ambiguousRetry = false;
      const baseline =
        state.replayRecord && state.replayRecord.responseBaseline;
      if (isReplay) {
        if (baseline != null) {
          replayMatched = responsesEqual(body, baseline);
          if (!replayMatched) {
            renderError({
              httpStatus: response.status,
              code: "replay_mismatch",
              message:
                "Exact replay failed: parsed response differs from the prior response.",
              details: {
                prior_request_id: baseline.request_id,
                replay_request_id: body && body.request_id,
              },
            });
            setText(els.replayStatus, "Exact replay mismatch.");
            return;
          }
        } else {
          // First submission never observed a response; this is a retry of the
          // exact submitted request, not an equivalence proof.
          ambiguousRetry = true;
        }
      }

      if (state.replayRecord) {
        state.replayRecord.responseBaseline = body;
      }
      state.historyBody = body;
      renderSuccess(body, { replayMatched, ambiguousRetry });
    } catch (_err) {
      // Network failure after submission: replayRecord already holds the exact
      // payload and API base for Retry via Replay.
      renderError({
        network: true,
        message:
          "Could not reach /v1/mind-turn. Prior answers are not shown as current.",
      });
    } finally {
      endRequest();
    }
  }

  async function onAsk() {
    if (!state.template || !state.ready || state.inFlight) {
      return;
    }
    const payload = buildAskPayload();
    const submittedApiBase = apiBase();
    await postMindTurn(payload, submittedApiBase, { isReplay: false });
  }

  async function onReplay() {
    if (!state.replayRecord || state.inFlight) {
      return;
    }
    // Always use the captured endpoint and payload — never the edited API base.
    await postMindTurn(
      state.replayRecord.submittedPayload,
      state.replayRecord.submittedApiBase,
      { isReplay: true },
    );
  }

  async function boot() {
    try {
      await loadTemplate();
      setText(els.readyStatus, "Template loaded. Checking readiness…");
      els.readyStatus.className = "status pending";
      setReadyUi();
      await checkReadiness();
    } catch (err) {
      state.ready = false;
      setText(
        els.readyStatus,
        err && err.message ? err.message : "Failed to load demo-request.json",
      );
      els.readyStatus.className = "status error";
      setReadyUi();
    }
  }

  els.checkReady.addEventListener("click", () => {
    checkReadiness();
  });
  els.ask.addEventListener("click", () => {
    onAsk();
  });
  els.replay.addEventListener("click", () => {
    onReplay();
  });
  els.apiBase.addEventListener("change", () => {
    state.ready = false;
    setText(els.readyStatus, "API base changed — re-check readiness.");
    els.readyStatus.className = "status pending";
    setText(els.readyRevision, "");
    // Replay stays bound to replayRecord.submittedApiBase, not the edited field.
    setReadyUi();
  });

  boot();
})();
