import { useState } from "react";
import { ChevronIcon, SparkleIcon } from "./Icons.jsx";

const EXAMPLES = [
  "I'm a public school teacher with two kids, renting in Brooklyn. I have $40K in student loans.",
  "I'm a retired veteran on a fixed income. I get healthcare through the VA.",
  "I'm a small business owner. Two employees, no health insurance, just bought my first home.",
];

export default function PersonalizePanel({ value, onChange }) {
  const [open, setOpen] = useState(false);

  const filled = value.trim().length > 0;
  const charCount = value.length;

  return (
    <section className={`personalize ${filled ? "filled" : ""}`}>
      <button
        type="button"
        className="personalize-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <SparkleIcon size={16} />
        <span className="personalize-title">
          {filled
            ? "Personalized impact on"
            : "Personalize: see how votes affect you"}
        </span>
        {filled && <span className="personalize-pill">on</span>}
        <ChevronIcon open={open} size={18} />
      </button>

      {open && (
        <div className="personalize-body">
          <p className="personalize-help">
            Tell Claude a bit about yourself — job, family, finances, where you
            live, what you care about. Each vote will get a "What this might
            mean for you" paragraph tailored to your situation. Optional, stays
            in your browser.
          </p>
          <textarea
            className="personalize-textarea"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="e.g., 'I'm a public school teacher with two kids, renting in Brooklyn. I have $40K in student loans.'"
            rows={4}
            maxLength={500}
          />
          <div className="personalize-footer">
            <div className="personalize-examples">
              <span className="personalize-examples-label">Try:</span>
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  className="personalize-example"
                  onClick={() => onChange(ex)}
                >
                  Example {i + 1}
                </button>
              ))}
            </div>
            <span className="personalize-count">{charCount} / 500</span>
          </div>
        </div>
      )}
    </section>
  );
}
