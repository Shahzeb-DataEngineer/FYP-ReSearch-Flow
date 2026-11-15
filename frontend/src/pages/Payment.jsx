import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { CreditCard, Smartphone, Wallet, ArrowLeft, ShieldCheck } from "lucide-react";

const methodList = [
  { icon: CreditCard, title: "Card", desc: "Visa, MasterCard, AmEx" },
  { icon: Smartphone, title: "Amazon Pay", desc: "Pay with your Amazon wallet" },
  { icon: Wallet, title: "UPI / Other Wallets", desc: "Regional wallets and UPI" },
];

const planLookup = {
  basic: { name: "Basic", price: "Free" },
  premium: { name: "Premium", price: "$50/mo" },
  advanced: { name: "Advanced", price: "$100/mo" },
};

const inputClass =
  "w-full bg-surface border border-faint rounded-lg px-3 py-2 text-sm text-ink placeholder-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

export default function Payment() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const planKey = (params.get("plan") || "basic").toLowerCase();
  const selectedPlan = planLookup[planKey] || planLookup.basic;
  const [selectedMethod, setSelectedMethod] = useState(methodList[0].title);

  const renderForm = () => {
    switch (selectedMethod) {
      case "Card":
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-ink mb-1">Cardholder name</label>
              <input className={inputClass} placeholder="Name on card" />
            </div>
            <div>
              <label className="block text-sm text-ink mb-1">Card number</label>
              <input className={inputClass} placeholder="1234 5678 9012 3456" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-ink mb-1">Expiry</label>
                <input className={inputClass} placeholder="MM/YY" />
              </div>
              <div>
                <label className="block text-sm text-ink mb-1">CVV</label>
                <input className={inputClass} placeholder="123" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="save-card" className="rounded border-faint accent-accent" />
              <label htmlFor="save-card" className="text-sm text-muted">Save card for faster checkout</label>
            </div>
          </div>
        );
      case "Amazon Pay":
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-ink mb-1">Amazon account email</label>
              <input className={inputClass} placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-sm text-ink mb-1">Mobile (for OTP)</label>
              <input className={inputClass} placeholder="+1 555 123 4567" />
            </div>
            <p className="text-xs text-muted">You will be redirected to Amazon to complete payment.</p>
          </div>
        );
      case "UPI / Other Wallets":
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-ink mb-1">Wallet / UPI ID</label>
              <input className={inputClass} placeholder="yourname@upi or wallet ID" />
            </div>
            <div>
              <label className="block text-sm text-ink mb-1">Country</label>
              <input className={inputClass} placeholder="Country" />
            </div>
            <div>
              <label className="block text-sm text-ink mb-1">Mobile</label>
              <input className={inputClass} placeholder="+91 98765 43210" />
            </div>
            <p className="text-xs text-muted">We’ll request an authorization in your wallet app.</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-paper">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-sm text-muted hover:text-ink mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        <div className="mb-8">
          <p className="text-sm text-muted mb-1">Selected plan</p>
          <h1 className="font-display text-3xl font-semibold text-ink">
            {selectedPlan.name} <span className="text-muted text-lg">({selectedPlan.price})</span>
          </h1>
          <p className="text-muted mt-2">
            Choose a payment method to continue. This is a placeholder flow — integrate your payment provider here.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {methodList.map((method) => (
            <button
              key={method.title}
              onClick={() => setSelectedMethod(method.title)}
              className={`border rounded-2xl p-4 text-left transition-colors ${
                selectedMethod === method.title
                  ? "border-accent bg-accent-tint shadow-sm"
                  : "border-faint bg-surface hover:border-accent/50 hover:shadow-sm"
              }`}
            >
              <div className="flex items-center gap-3">
                <method.icon className={`w-5 h-5 ${selectedMethod === method.title ? "text-accent" : "text-muted"}`} />
                <div>
                  <p className="text-sm font-semibold text-ink">{method.title}</p>
                  <p className="text-xs text-muted">{method.desc}</p>
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="mt-8 bg-surface border border-faint rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="w-4 h-4 text-accent" />
            <p className="text-sm font-semibold text-ink">
              Enter payment details ({selectedMethod})
            </p>
          </div>
          {renderForm()}
          <div className="mt-6 flex items-center gap-3">
            <button className="px-4 py-2.5 rounded-full bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors">
              Pay now
            </button>
            <button
              onClick={() => navigate("/pricing")}
              className="text-sm text-muted hover:text-ink underline"
            >
              Back to pricing
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
