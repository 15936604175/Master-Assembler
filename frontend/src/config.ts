import { getVersion } from '@tauri-apps/api/app';

// GitHub 仓库配置
export const GITHUB_OWNER = '15936604175';
export const GITHUB_REPO = 'X-Intelligence';

// 从 Tauri 运行时获取版本号（Cargo.toml 是唯一来源）
export async function getAppVersion(): Promise<string> {
  try {
    return await getVersion();
  } catch {
    return '0.0.0'; // 开发模式下回退
  }
}
