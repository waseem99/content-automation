const fs = require('node:fs');
const path = require('node:path');

function clean(value) {
  return String(value || '').replace(/\u001b\[[0-9;]*m/g, '').trim();
}

class PlatformReporter {
  constructor(options = {}) {
    this.outputDir = options.outputDir || path.join('.runtime', 'e2e', 'latest');
    this.results = [];
    this.startedAt = new Date();
  }

  onBegin(_config, suite) {
    fs.mkdirSync(this.outputDir, { recursive: true });
    this.total = suite.allTests().length;
  }

  onTestEnd(test, result) {
    const annotations = Object.fromEntries(
      test.annotations.filter((item) => item.type).map((item) => [item.type, item.description || true])
    );
    this.results.push({
      title: test.titlePath().join(' › '),
      file: test.location.file,
      line: test.location.line,
      project: test.parent?.project()?.name || null,
      status: result.status,
      duration_ms: result.duration,
      retry: result.retry,
      severity: annotations.severity || (result.status === 'passed' ? null : 'P1'),
      improvement: annotations.improvement || null,
      errors: result.errors.map((error) => clean(error.message || error.stack))
    });
  }

  onEnd(result) {
    const endedAt = new Date();
    const failed = this.results.filter((item) => !['passed', 'skipped'].includes(item.status));
    const skipped = this.results.filter((item) => item.status === 'skipped');
    const passed = this.results.filter((item) => item.status === 'passed');
    const improvements = this.results.filter((item) => item.improvement);
    const summary = {
      kind: 'platform_e2e_summary',
      status: result.status,
      started_at: this.startedAt.toISOString(),
      ended_at: endedAt.toISOString(),
      duration_ms: endedAt - this.startedAt,
      total: this.results.length,
      passed: passed.length,
      failed: failed.length,
      skipped: skipped.length,
      improvements: improvements.length,
      results: this.results
    };

    fs.writeFileSync(path.join(this.outputDir, 'summary.json'), JSON.stringify(summary, null, 2));

    const markdown = [
      '# Automated Platform Acceptance',
      '',
      `- Result: **${result.status.toUpperCase()}**`,
      `- Passed: **${passed.length}**`,
      `- Failed: **${failed.length}**`,
      `- Skipped: **${skipped.length}**`,
      `- Improvements noted: **${improvements.length}**`,
      `- Completed: ${endedAt.toISOString()}`,
      '',
      '## Failures',
      '',
      ...(failed.length ? failed.map((item) => `- **${item.severity || 'P1'}** — ${item.title}\n  - ${item.errors[0] || item.status}`) : ['No automated failures.']),
      '',
      '## Improvements',
      '',
      ...(improvements.length ? improvements.map((item) => `- ${item.title}: ${item.improvement}`) : ['No explicit improvement annotations.']),
      '',
      '## Release interpretation',
      '',
      result.status === 'passed'
        ? 'This run passed its configured scope. Production confidence still requires three consecutive full no-cost runs and one separately approved live-provider proof.'
        : 'This run is not release-ready. Resolve P0/P1 findings, rerun, and retain the new evidence.'
    ].join('\n');
    fs.writeFileSync(path.join(this.outputDir, 'summary.md'), markdown);

    const defects = failed.length
      ? failed.map((item) => `## ${item.severity || 'P1'} — ${item.title}\n\n${item.errors.join('\n\n') || item.status}\n`).join('\n')
      : '# Defects\n\nNo defects were detected in this run.\n';
    fs.writeFileSync(path.join(this.outputDir, 'defects.md'), defects);

    const improvementText = improvements.length
      ? improvements.map((item) => `- ${item.title}: ${item.improvement}`).join('\n')
      : 'No explicit improvements were recorded.';
    fs.writeFileSync(path.join(this.outputDir, 'improvements.md'), `# Improvements\n\n${improvementText}\n`);
  }
}

module.exports = PlatformReporter;
