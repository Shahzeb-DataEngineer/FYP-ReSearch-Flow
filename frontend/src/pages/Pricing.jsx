import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { CheckCircle2, Crown, ShieldCheck, Zap, ArrowLeft } from "lucide-react";

const plans = [
  {
    name: "Basic",
    price: "Free",
    badge: "Start here",
    planValue: "basic",
    features: [
      "Unlimited searches (rate limited)",
      "Save searches locally",
      "Export to PDF/Excel",
      "Access to citation mesh viewer",
    ],
    cta: "Start for Free",
    accent: "border-faint",
    highlight: false,
  },
  {
    name: "Premium",
    price: "$50",
    badge: "Most popular",
    planValue: "premium",
    features: [
      "Access to paid research papers",
      "Priority search throughput",
      "Cloud saved searches",
      "Advanced filters & sorting",
      "Enhanced export (metadata sheets)",
      "Email support",
    ],
    cta: "Get Premium",
    accent: "border-faint",
    highlight: false,
  },
  {
    name: "Advanced",
    price: "$100",
    badge: "For teams",
    planValue: "advanced",
    features: [
      "All Premium features",
      "Team seats & collaboration",
      "API access & higher limits",
      "Priority support",
      "Custom onboarding",
    ],
    cta: "Get Advanced",
    accent: "border-faint",
    highlight: false,
  },
];

export default function Pricing() {
  const navigate = useNavigate();
  const [selectedPlan, setSelectedPlan] = useState("premium");

  const goToPayment = (planValue) => {
    if (planValue === "basic") {
      navigate("/");
    } else {
      navigate(`/payment?plan=${planValue}`);
    }
  };

  return (
    <div className="bg-paper">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-sm text-muted hover:text-ink mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent text-white text-sm font-medium mb-3">
            <Crown className="w-4 h-4" />
            Choose your plan
          </div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold text-ink mb-3">
            Simple pricing for every researcher
          </h1>
          <p className="text-muted text-lg">
            Start free, upgrade when you need more power.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isActive = selectedPlan === plan.planValue;
            return (
              <div
                key={plan.name}
                onClick={() => setSelectedPlan(plan.planValue)}
                className={`border rounded-2xl p-6 flex flex-col cursor-pointer transition-colors ${
                  isActive ? "border-accent shadow-md bg-accent-tint" : "border-faint bg-surface hover:border-accent/50"
                }`}
              >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs font-semibold bg-accent-tint text-accent rounded-full px-2.5 py-1 inline-block">{plan.badge}</p>
                  <h2 className="text-xl font-semibold text-ink mt-2">
                    {plan.name}
                  </h2>
                </div>
                {plan.highlight ? (
                  <ShieldCheck className="w-6 h-6 text-accent" />
                ) : (
                  <Zap className="w-6 h-6 text-muted" />
                )}
              </div>

              <div className="mb-6">
                <span className="text-3xl font-semibold text-ink">
                  {plan.price}
                </span>
                {plan.price !== "Free" && (
                  <span className="text-muted text-sm"> / month</span>
                )}
              </div>

              <ul className="space-y-3 mb-6">
                {plan.features.map((feat) => (
                  <li key={feat} className="flex items-center gap-2 text-sm text-muted">
                    <CheckCircle2 className="w-4 h-4 text-accent" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => goToPayment(plan.planValue)}
                className={`w-full py-2.5 rounded-full text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-accent text-white hover:bg-accent-hover"
                    : "bg-surface border border-faint text-ink hover:bg-fill"
                }`}
              >
                {plan.cta}
              </button>
            </div>
            );
          })}
        </div>


      </div>
    </div>
  );
}
