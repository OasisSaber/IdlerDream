import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  CoreStatus,
  CurrentProjectState,
  InspectionPermission,
} from "@idlerdream/protocol";
import { InspectionReliabilityCard } from "./InspectionReliabilityCard";

function state(overrides: Partial<CurrentProjectState> = {}): CurrentProjectState {
  return {
    project_id: "6a5ad7a8-7d1e-4d5b-9f7a-2c3d4e5f6a7b",
    core_status: "in_progress" as CoreStatus,
    phase: "testing",
    summary: "正在验证测试套件。",
    next_action: { actor: "agent", action: "修复失败的测试。" },
    confidence: 0.82,
    freshness: "current",
    activity_state: "active",
    facts: [],
    inferences: [],
    risks: [],
    progress: { mode: "none", completed: null, total: null },
    workspace_fingerprint: "fp-1",
    verified_at: "2026-08-06T00:00:00Z",
    updated_at: "2026-08-06T00:00:00Z",
    needs_user_attention: false,
    inspection_quality: "full",
    inspection_warnings: [],
    inspection_error: null,
    ...overrides,
  };
}

describe("InspectionReliabilityCard", () => {
  it("renders the full state with a FULL badge and no warning details", () => {
    render(
      <InspectionReliabilityCard
        state={state()}
        permission={"standard_source" as InspectionPermission}
      />,
    );
    expect(screen.getByRole("heading", { name: "完整巡检结果" })).toBeInTheDocument();
    expect(screen.getByText("FULL")).toBeInTheDocument();
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(screen.getByText("标准源码")).toBeInTheDocument();
  });

  it("renders the partial state with warnings in native details/summary", () => {
    const warnings = [
      "Normalizer: defaulted inferences[0].kind to model.",
      "Normalizer: converted confidence percent to fraction.",
    ];
    render(
      <InspectionReliabilityCard
        state={state({ inspection_quality: "partial", inspection_warnings: warnings })}
        permission={"restricted" as InspectionPermission}
      />,
    );
    expect(screen.getByRole("heading", { name: "部分有效巡检" })).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
    expect(screen.getByText("2 项标准化说明")).toBeInTheDocument();
    expect(screen.getByText(warnings[0])).toBeInTheDocument();
    expect(screen.getByText("受限读取")).toBeInTheDocument();
  });

  it("renders the failed state with an error surfaced via role=status", () => {
    render(
      <InspectionReliabilityCard
        state={state({
          inspection_quality: "failed",
          inspection_error: "workspace fingerprint mismatch",
        })}
        permission={"local_only" as InspectionPermission}
      />,
    );
    expect(screen.getByRole("heading", { name: "巡检尚未验证" })).toBeInTheDocument();
    expect(screen.getByText("UNVERIFIED")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("workspace fingerprint mismatch");
    expect(screen.getByText("仅本地")).toBeInTheDocument();
  });

  it("caps the visible warning list at six items", () => {
    const warnings = Array.from(
      { length: 8 },
      (_, index) => `Normalizer: warning number ${index + 1}.`,
    );
    render(
      <InspectionReliabilityCard
        state={state({ inspection_quality: "partial", inspection_warnings: warnings })}
        permission={"standard_source" as InspectionPermission}
      />,
    );
    expect(screen.getByText("8 项标准化说明")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.queryByText("Normalizer: warning number 7.")).not.toBeInTheDocument();
  });

  it("renders a long Chinese warning without truncating it", () => {
    const longWarning =
      "Normalizer：模型未提供可靠下一步动作，已保留为 none；" +
      "同时将置信度百分比转换为小数，并丢弃了缺少摘要的无效证据条目。";
    render(
      <InspectionReliabilityCard
        state={state({
          inspection_quality: "partial",
          inspection_warnings: [longWarning],
        })}
        permission={"standard_source" as InspectionPermission}
      />,
    );
    expect(screen.getByText(longWarning)).toBeInTheDocument();
  });
});
