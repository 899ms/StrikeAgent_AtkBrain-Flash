import { useT } from "../i18n";

/** 集群子项目多选操作条。 */

export function BatchSelectionBar({
  count,
  noun,
  busy,
  onRun,
  onPause,
  onDelete,
  onClear,
}: {
  count: number;
  noun?: string;
  busy: boolean;
  onRun: () => void;
  onPause: () => void;
  onDelete: () => void;
  onClear: () => void;
}) {
  const { t } = useT();
  const label = noun ?? t("batch.child");
  if (count <= 0) return null;
  return (
    <div className="batch-toolbar">
      <b>{t("batch.selected", { n: count, noun: label })}</b>
      <button className="btn btn-primary btn-sm" disabled={busy} onClick={onRun}>{t("common.run")}</button>
      <button className="btn btn-secondary btn-sm" disabled={busy} onClick={onPause}>{t("common.pause")}</button>
      <button className="btn btn-danger btn-sm" disabled={busy} onClick={onDelete}>{t("common.delete")}</button>
      <button className="btn btn-secondary btn-sm" disabled={busy} onClick={onClear}>{t("projects.clearSelect")}</button>
    </div>
  );
}
