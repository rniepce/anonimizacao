interface Props {
    title: string;
    status: string;
    progress: number;
}

function ProgressSection({ title, status, progress }: Props) {
    return (
        <section className="progress-section glass-card">
            <div className="progress-header">
                <div className="spinner" />
                <h3>{title}</h3>
            </div>
            <div className="progress-bar">
                <div
                    className="progress-fill"
                    style={{ width: `${progress}%` }}
                />
            </div>
            <p className="progress-status">{status}</p>
        </section>
    );
}

export default ProgressSection;
