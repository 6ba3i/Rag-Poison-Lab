import type { LlmProviderOption, LlmRoleConfig, ProviderName } from "../api/types";

interface LlmSelectorProps {
  roleLabel: string;
  value: LlmRoleConfig;
  providerOptions: LlmProviderOption[];
  onChange: (value: LlmRoleConfig) => void;
}

interface StatusDescriptor {
  label: string;
  className: string;
}

function getStatus(value: LlmRoleConfig, option: LlmProviderOption | undefined): StatusDescriptor {
  if (!option) {
    return {
      label: "Missing key",
      className: "border-rose-500/70 bg-rose-950/20 text-rose-300",
    };
  }

  if (value.provider !== "local" && !option.available) {
    return {
      label: "Missing key",
      className: "border-rose-500/70 bg-rose-950/20 text-rose-300",
    };
  }

  if (value.provider === "local" && !option.models.includes(value.model)) {
    return {
      label: "Local model not installed",
      className: "border-amber-500/70 bg-amber-950/20 text-amber-300",
    };
  }

  return {
    label: "Ready",
    className: "border-emerald-500/70 bg-emerald-950/20 text-emerald-300",
  };
}

export function LlmSelector({ roleLabel, value, providerOptions, onChange }: LlmSelectorProps): JSX.Element {
  const selectedOption = providerOptions.find((item) => item.provider === value.provider);
  const status = getStatus(value, selectedOption);

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
    <section className="panel p-4">
      <h3 className="text-base font-semibold text-slate-100">{roleLabel}</h3>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm text-slate-300">
          Provider
          <select
            value={value.provider}
            onChange={(event) => handleProviderChange(event.target.value as ProviderName)}
            className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 outline-none transition-colors duration-150 focus:border-slate-400"
          >
            {providerOptions.map((option) => (
              <option
                key={option.provider}
                value={option.provider}
                disabled={option.provider !== "local" && !option.available}
              >
                {option.provider}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-2 text-sm text-slate-300">
          Model
          <select
            value={value.model}
            onChange={(event) => onChange({ ...value, model: event.target.value })}
            className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 outline-none transition-colors duration-150 focus:border-slate-400"
          >
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4">
        <span className={["rounded-md border px-2 py-1 text-xs", status.className].join(" ")}>{status.label}</span>
      </div>
    </section>
  );
}
