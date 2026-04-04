import type { LlmProviderOption, LlmRoleConfig, ProviderName } from "../api/types";

interface LlmSelectorProps {
  roleLabel: string;
  value: LlmRoleConfig;
  providerOptions: LlmProviderOption[];
  onChange: (value: LlmRoleConfig) => void;
}

interface StatusDescriptor {
  label: string;
  tone: "success" | "warning" | "danger";
}

function getStatus(value: LlmRoleConfig, option: LlmProviderOption | undefined): StatusDescriptor {
  if (!option) {
    return { label: "Missing provider", tone: "danger" };
  }

  if (value.provider !== "local" && !option.available) {
    return { label: "Missing API key", tone: "danger" };
  }

  if (value.provider === "local" && !option.models.includes(value.model)) {
    return { label: "Local model unavailable", tone: "warning" };
  }

  return { label: "Ready", tone: "success" };
}

export function LlmSelector({ roleLabel, value, providerOptions, onChange }: LlmSelectorProps): JSX.Element {
  const selectedOption = providerOptions.find((item) => item.provider === value.provider);
  const status = getStatus(value, selectedOption);
  const roleToneClass = roleLabel.toLowerCase().includes("victim") ? "settings-section-victim" : "settings-section-attacker";

  const modelOptions = selectedOption ? [...selectedOption.models] : [];
  if (!modelOptions.includes(value.model)) {
    modelOptions.unshift(value.model);
  }

  function handleProviderChange(provider: ProviderName): void {
    const option = providerOptions.find((item) => item.provider === provider);
    const nextModel = option && option.models.length > 0 ? option.models[0] : value.model;
    onChange({ provider, model: nextModel });
  }

  return (
    <section className={["surface", "settings-section", roleToneClass].join(" ")}>
      <div className="status-row">
        <h3 className="card-title">{roleLabel}</h3>
        <span className={["badge", "mono", status.tone].join(" ")}>{status.label}</span>
      </div>

      <div className="form-grid" style={{ marginTop: 16 }}>
        <label className="field">
          <span className="field-label">Provider</span>
          <select
            value={value.provider}
            onChange={(event) => handleProviderChange(event.target.value as ProviderName)}
            className="select"
          >
            {providerOptions.map((option) => (
              <option key={option.provider} value={option.provider} disabled={option.provider !== "local" && !option.available}>
                {option.provider}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Model</span>
          <select value={value.model} onChange={(event) => onChange({ ...value, model: event.target.value })} className="select">
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
