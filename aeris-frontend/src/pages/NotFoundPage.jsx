import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <section className="card">
      <div className="card__head">
        <h2>This page does not exist</h2>
        <p><Link to="/">Return to the overview</Link></p>
      </div>
    </section>
  )
}
