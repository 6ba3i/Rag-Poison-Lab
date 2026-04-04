interface JsonSection {
  title: string;
  payload: unknown;
}

interface JsonResultDrawerProps {
  open: boolean;
  title: string;
  sections: JsonSection[];
  onClose: () => void;
}

export function JsonResultDrawer({ open, title, sections, onClose }: JsonResultDrawerProps): JSX.Element {
  return (
    <>
      {open ? <button type="button" className="drawer-backdrop" aria-label="Close JSON drawer" onClick={onClose} /> : null}
      <aside className={["json-drawer", open ? "open" : ""].join(" ")} aria-hidden={!open}>
        <div className="json-drawer-header">
          <div>
            <h3 className="section-title" style={{ fontSize: 18 }}>
              {title}
            </h3>
            <p className="section-caption" style={{ marginTop: 4 }}>
              Developer/debug payloads for this run.
            </p>
          </div>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="stack" style={{ marginTop: 14 }}>
          {sections.map((section) => (
            <div key={section.title} className="surface-elevated">
              <p className="text-meta" style={{ margin: 0 }}>
                {section.title}
              </p>
              <pre className="code-block" style={{ marginTop: 8 }}>
                {JSON.stringify(section.payload ?? null, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
