import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { InspectionJob } from "@idlerdream/protocol";
import { InspectionPanel } from "./InspectionPanel";

function job(overrides: Partial<InspectionJob> = {}): InspectionJob {
  return {
    id: "job-1",
    project_id: "6a5ad7a8-7d1e-4d5b-9f7a-2c3d4e5f6a7b",
    source: "manual",
    status: "running",
    stage: "semantic_inspection",
    started_at: "2026-08-06T00:00:00Z",
    finished_at: null,
    elapsed_seconds: 128,
    last_activity: "正在读取过滤后的巡检快照",
    error: null,
    warnings: [],
    budget: { max_files: 40, max_content_mb: 2, max_tool_calls: 100 },
    ...overrides,
  };
}

describe("InspectionPanel", () => {
  it("maps machine stage keys to readable labels and marks prior steps done", () => {
    render(<InspectionPanel job={job()} projectName="IdlerDream" onCancel={() => {}} />);
    expect(screen.getByRole("heading", { name: "正在巡检" })).toBeInTheDocument();
    expect(screen.getAllByText("只读语义巡检").length).toBeGreaterThan(0);
    expect(screen.getByText("生成事实基线")).toBeInTheDocument();
    expect(screen.getByText("建立隔离快照")).toBeInTheDocument();
    expect(screen.getByText("校验并归并报告")).toBeInTheDocument();
    expect(screen.getByText("进行中")).toBeInTheDocument();
  });

  it("shows real budget ceilings instead of fake usage", () => {
    render(<InspectionPanel job={job()} projectName="IdlerDream" onCancel={() => {}} />);
    expect(screen.getAllByText("2:08").length).toBeGreaterThan(0);
    expect(screen.getAllByText("40").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
  });

  it("surfaces the latest normalization warning via role=status", () => {
    render(
      <InspectionPanel
        job={job({ warnings: ["first", "latest warning"] })}
        projectName="IdlerDream"
        onCancel={() => {}}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("latest warning");
  });

  it("exposes an accessible label and a working cancel action", () => {
    const onCancel = vi.fn();
    render(<InspectionPanel job={job()} projectName="智能座舱毕业设计" onCancel={onCancel} />);
    expect(screen.getByLabelText("智能座舱毕业设计 的只读巡检进度")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /取消巡检/ })[0]);
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
