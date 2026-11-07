export default function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <span className="brand">Bagodi</span>
        <span className="environment">Foundation</span>
      </header>
      <section className="content">
        <p className="eyebrow">BAGODI E-COMMERCE PLATFORM</p>
        <h1>Customer shopping application foundation</h1>
        <p className="description">The live catalogue, cart, checkout and customer account will be connected to implemented backend APIs. No products are displayed until the catalogue API returns real records.</p>
        <div className="notice" role="status">
          Application foundation is running. Business data will appear only after real API integration.
        </div>
      </section>
    </main>
  );
}
