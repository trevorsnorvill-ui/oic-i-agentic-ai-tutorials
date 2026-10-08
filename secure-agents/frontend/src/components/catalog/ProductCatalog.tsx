import { useState, useEffect, useCallback } from "react";
import {
  Button,
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Modal,
  TextInput,
  NumberInput,
  InlineNotification,
  Tag,
  Stack,
  DataTableSkeleton,
} from "@carbon/react";
import { Add, TrashCan, Edit, SortAscending, SortDescending, Renew } from "@carbon/icons-react";

interface Product {
  id?: string;
  name: string;
  price: number;
}

interface ApiResult {
  success: boolean;
  message: string;
  products?: Product[];
  count?: number;
}

const API = import.meta.env.VITE_API_URL || "";

function authHeader(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...authHeader(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export default function ProductCatalog() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState<boolean | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Modal state
  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [formName, setFormName] = useState("");
  const [formPrice, setFormPrice] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const clearMessages = () => { setError(null); setSuccessMsg(null); };

  const loadProducts = useCallback(async (sortDir: boolean | null = null, search = "") => {
    setLoading(true);
    clearMessages();
    try {
      let data: ApiResult;
      if (search.trim()) {
        data = await apiFetch(`/api/v1/mcp/products/search?name=${encodeURIComponent(search)}`);
      } else if (sortDir !== null) {
        data = await apiFetch(`/api/v1/mcp/products/sort?ascending=${sortDir}&limit=100`);
      } else {
        data = await apiFetch("/api/v1/mcp/products?limit=100");
      }
      setProducts(data.products ?? []);
    } catch (e: any) {
      setError(e.message);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadProducts(); }, [loadProducts]);

  const handleSearch = (val: string) => {
    setSearchQuery(val);
    setSortAsc(null);
    loadProducts(null, val);
  };

  const handleSort = (asc: boolean) => {
    setSortAsc(asc);
    setSearchQuery("");
    loadProducts(asc, "");
  };

  const handleCreate = async () => {
    setSubmitting(true);
    clearMessages();
    try {
      const data: ApiResult = await apiFetch("/api/v1/mcp/products", {
        method: "POST",
        body: JSON.stringify({ name: formName, price: formPrice }),
      });
      setSuccessMsg(data.message);
      setShowCreate(false);
      loadProducts(sortAsc, searchQuery);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedProduct?.id) return;
    setSubmitting(true);
    clearMessages();
    try {
      const data: ApiResult = await apiFetch(`/api/v1/mcp/products/${selectedProduct.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: formName, price: formPrice }),
      });
      setSuccessMsg(data.message);
      setShowEdit(false);
      loadProducts(sortAsc, searchQuery);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedProduct?.id) return;
    setSubmitting(true);
    clearMessages();
    try {
      const data: ApiResult = await apiFetch(`/api/v1/mcp/products/${selectedProduct.id}`, {
        method: "DELETE",
      });
      setSuccessMsg(data.message);
      setShowDelete(false);
      loadProducts(sortAsc, searchQuery);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const openCreate = () => { setFormName(""); setFormPrice(0); clearMessages(); setShowCreate(true); };
  const openEdit = (p: Product) => { setSelectedProduct(p); setFormName(p.name); setFormPrice(p.price); clearMessages(); setShowEdit(true); };
  const openDelete = (p: Product) => { setSelectedProduct(p); clearMessages(); setShowDelete(true); };

  const headers = [
    { key: "id", header: "ID" },
    { key: "name", header: "Name" },
    { key: "price", header: "Price" },
    { key: "actions", header: "Actions" },
  ];

  const rows = products.map((p) => ({
    id: p.id ?? p.name,
    name: p.name,
    price: `$${p.price.toFixed(2)}`,
    actions: p,
  }));

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-cds-text-primary">Product Catalog</h1>
          <p className="mt-1 text-sm text-cds-text-secondary">
            Calls the MCP server with your IBM Verify JWT →
            Vault issues scoped MongoDB credentials → products returned
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tag type="blue">JWT auth</Tag>
          <Tag type="green">Vault creds</Tag>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={clearMessages}
          className="mb-4"
        />
      )}
      {successMsg && (
        <InlineNotification
          kind="success"
          title="Success"
          subtitle={successMsg}
          onCloseButtonClick={clearMessages}
          className="mb-4"
        />
      )}

      {/* Table */}
      <DataTable rows={rows} headers={headers}>
        {({ rows: tableRows, headers: tableHeaders, getTableProps, getHeaderProps, getRowProps }: any) => (
          <>
            <TableToolbar>
              <TableToolbarContent>
                <TableToolbarSearch
                  value={searchQuery}
                  onChange={(e: any) => handleSearch(e.target.value)}
                  placeholder="Search by name..."
                />
                <Button
                  kind="ghost"
                  size="sm"
                  renderIcon={sortAsc === true ? SortAscending : SortDescending}
                  iconDescription="Sort by price"
                  hasIconOnly={false}
                  onClick={() => handleSort(sortAsc !== true)}
                >
                  {sortAsc === true ? "Price: Low→High" : sortAsc === false ? "Price: High→Low" : "Sort by price"}
                </Button>
                <Button
                  kind="ghost"
                  size="sm"
                  renderIcon={Renew}
                  iconDescription="Refresh"
                  hasIconOnly
                  onClick={() => { setSortAsc(null); setSearchQuery(""); loadProducts(); }}
                />
                <Button renderIcon={Add} onClick={openCreate} size="sm">
                  Add product
                </Button>
              </TableToolbarContent>
            </TableToolbar>

            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {tableHeaders.map((h: any) => (
                    <TableHeader {...getHeaderProps({ header: h })} key={h.key}>
                      {h.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <div className="py-4 text-center text-cds-text-secondary">Loading…</div>
                    </TableCell>
                  </TableRow>
                ) : tableRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <p className="py-4 text-center text-cds-text-secondary">
                        No products found.{" "}
                        <button className="text-cds-link-primary underline" onClick={openCreate}>
                          Add one?
                        </button>
                      </p>
                    </TableCell>
                  </TableRow>
                ) : (
                  tableRows.map((row: any) => {
                    const product = products.find((p) => (p.id ?? p.name) === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell: any) => {
                          if (cell.info.header === "actions") {
                            return (
                              <TableCell key={cell.id}>
                                <div className="flex gap-2">
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    renderIcon={Edit}
                                    iconDescription="Edit"
                                    hasIconOnly
                                    onClick={() => product && openEdit(product)}
                                  />
                                  <Button
                                    kind="danger--ghost"
                                    size="sm"
                                    renderIcon={TrashCan}
                                    iconDescription="Delete"
                                    hasIconOnly
                                    onClick={() => product && openDelete(product)}
                                  />
                                </div>
                              </TableCell>
                            );
                          }
                          return <TableCell key={cell.id}>{cell.value}</TableCell>;
                        })}
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </>
        )}
      </DataTable>

      {/* Flow explanation */}
      <div className="mt-6 rounded border border-cds-border-subtle bg-cds-layer p-4 text-sm text-cds-text-secondary">
        <p className="font-semibold text-cds-text-primary">Security flow for each request</p>
        <ol className="mt-2 list-decimal pl-5 leading-relaxed">
          <li>Frontend sends your IBM Verify <strong>access token</strong> to the backend proxy</li>
          <li>Backend forwards it to the <strong>MCP server</strong> as a Bearer token</li>
          <li>MCP verifies the JWT signature against IBM Verify's <strong>JWKS endpoint</strong></li>
          <li>MCP presents the token to <strong>Vault JWT auth</strong> to get a short-lived Vault token</li>
          <li>Vault maps your token's <code>groups</code> claim to an <strong>ACL policy</strong> (readonly / readwrite)</li>
          <li>Vault issues <strong>dynamic MongoDB credentials</strong> scoped to that policy (1h TTL)</li>
          <li>MCP connects to MongoDB with those credentials and returns the result</li>
        </ol>
      </div>

      {/* Create Modal */}
      <Modal
        open={showCreate}
        modalHeading="Add product"
        primaryButtonText="Create"
        secondaryButtonText="Cancel"
        onRequestSubmit={handleCreate}
        onRequestClose={() => setShowCreate(false)}
        primaryButtonDisabled={submitting || !formName || formPrice <= 0}
      >
        <Stack gap={5} className="mt-4">
          <TextInput
            id="create-name"
            labelText="Product name"
            value={formName}
            onChange={(e: any) => setFormName(e.target.value)}
          />
          <NumberInput
            id="create-price"
            label="Price ($)"
            value={formPrice}
            min={0.01}
            step={0.01}
            onChange={(_e: any, { value }: any) => setFormPrice(Number(value))}
          />
        </Stack>
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={showEdit}
        modalHeading={`Edit: ${selectedProduct?.name}`}
        primaryButtonText="Save"
        secondaryButtonText="Cancel"
        onRequestSubmit={handleUpdate}
        onRequestClose={() => setShowEdit(false)}
        primaryButtonDisabled={submitting || !formName || formPrice <= 0}
      >
        <Stack gap={5} className="mt-4">
          <TextInput
            id="edit-name"
            labelText="Product name"
            value={formName}
            onChange={(e: any) => setFormName(e.target.value)}
          />
          <NumberInput
            id="edit-price"
            label="Price ($)"
            value={formPrice}
            min={0.01}
            step={0.01}
            onChange={(_e: any, { value }: any) => setFormPrice(Number(value))}
          />
        </Stack>
      </Modal>

      {/* Delete Modal */}
      <Modal
        open={showDelete}
        danger
        modalHeading="Delete product"
        primaryButtonText="Delete"
        secondaryButtonText="Cancel"
        onRequestSubmit={handleDelete}
        onRequestClose={() => setShowDelete(false)}
        primaryButtonDisabled={submitting}
      >
        <p>
          Are you sure you want to delete <strong>{selectedProduct?.name}</strong>? This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
