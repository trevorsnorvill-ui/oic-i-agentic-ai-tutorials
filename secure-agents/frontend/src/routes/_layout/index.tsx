import { createFileRoute } from "@tanstack/react-router";
import ProductCatalog from "@/components/catalog/ProductCatalog";

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
});

function Dashboard() {
  return (
    <div className="py-8">
      <ProductCatalog />
    </div>
  );
}
