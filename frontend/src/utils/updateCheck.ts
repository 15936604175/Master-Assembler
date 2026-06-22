import { GITHUB_OWNER, GITHUB_REPO, getAppVersion } from '../config';

export interface GitHubRelease {
  tag_name: string;
  html_url: string;
  body: string | null;
  published_at: string;
}

export async function checkForUpdate(): Promise<GitHubRelease | null> {
  try {
    const [currentVer, url] = await Promise.all([
      getAppVersion(),
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
    ]);

    const res = await fetch(url, {
      headers: { Accept: 'application/vnd.github.v3+json' },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;

    const release: GitHubRelease = await res.json();
    const latestVer = release.tag_name.replace(/^v/, '');

    if (compareVersions(latestVer, currentVer) > 0) {
      return release;
    }
    return null;
  } catch {
    return null;
  }
}

function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na > nb) return 1;
    if (na < nb) return -1;
  }
  return 0;
}
