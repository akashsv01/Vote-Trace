import { useState } from "react";

export default function AddressInput({ onSubmit, disabled }) {
  const [address, setAddress] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!address.trim()) return;
    onSubmit(address.trim());
  }

  return (
    <form className="address-form" onSubmit={handleSubmit}>
      <input
        type="text"
        className="address-input"
        placeholder="Enter your home address (e.g., 1600 Pennsylvania Ave NW, Washington, DC)"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        disabled={disabled}
        autoFocus
      />
      <button
        type="submit"
        className="address-submit"
        disabled={disabled || !address.trim()}
      >
        {disabled ? "Looking up..." : "Find my reps"}
      </button>
    </form>
  );
}
