import { redirect } from "next/navigation";

// There is no billing: the pilot page states the terms and that pricing is not set.
export default function PricingPage() {
  redirect("/pilot#terms-h");
}
