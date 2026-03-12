/**
 * File upload utilities for drag-and-drop and file picker support.
 */

export interface UploadedFile {
  name: string;
  size: number;
  base64: string;
  type: string;
}

/**
 * Allowed file extensions for upload.
 * Covers common code, text, image, and data files.
 */
export const ALLOWED_TYPES: Record<string, string> = {
  // Code files
  '.ts': 'text/typescript',
  '.tsx': 'text/typescript',
  '.js': 'text/javascript',
  '.jsx': 'text/javascript',
  '.py': 'text/x-python',
  '.rs': 'text/x-rust',
  '.go': 'text/x-go',
  '.java': 'text/x-java',
  '.c': 'text/x-c',
  '.cpp': 'text/x-c++',
  '.h': 'text/x-c',
  '.hpp': 'text/x-c++',
  '.cs': 'text/x-csharp',
  '.rb': 'text/x-ruby',
  '.php': 'text/x-php',
  '.swift': 'text/x-swift',
  '.kt': 'text/x-kotlin',
  '.sh': 'text/x-shellscript',
  '.bat': 'text/x-bat',
  '.ps1': 'text/x-powershell',
  '.sql': 'text/x-sql',
  '.r': 'text/x-r',
  '.lua': 'text/x-lua',
  '.zig': 'text/x-zig',

  // Config / data
  '.json': 'application/json',
  '.yaml': 'text/yaml',
  '.yml': 'text/yaml',
  '.toml': 'text/toml',
  '.xml': 'text/xml',
  '.csv': 'text/csv',
  '.env': 'text/plain',
  '.ini': 'text/plain',
  '.cfg': 'text/plain',
  '.conf': 'text/plain',

  // Text / docs
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.rst': 'text/x-rst',
  '.log': 'text/plain',
  '.diff': 'text/x-diff',
  '.patch': 'text/x-diff',

  // Web
  '.html': 'text/html',
  '.htm': 'text/html',
  '.css': 'text/css',
  '.scss': 'text/x-scss',
  '.less': 'text/x-less',
  '.svg': 'image/svg+xml',

  // Images
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.bmp': 'image/bmp',
  '.ico': 'image/x-icon',

  // Documents
  '.pdf': 'application/pdf',

  // Docker / CI
  '.dockerfile': 'text/x-dockerfile',
  '.dockerignore': 'text/plain',
  '.gitignore': 'text/plain',
  '.editorconfig': 'text/plain',
};

/**
 * Check if a file extension is allowed for upload.
 */
function isAllowedFile(filename: string): boolean {
  const ext = getExtension(filename);
  // Allow extensionless files like Dockerfile, Makefile
  if (!ext) {
    const basename = filename.toLowerCase();
    return ['dockerfile', 'makefile', 'readme', 'license', 'changelog'].includes(basename);
  }
  return ext in ALLOWED_TYPES;
}

/**
 * Get file extension (lowercase, with dot).
 */
function getExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.');
  if (lastDot <= 0) return '';
  return filename.slice(lastDot).toLowerCase();
}

/**
 * Read a File object as base64.
 */
function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix (e.g., "data:text/plain;base64,")
      const base64 = result.split(',')[1] || result;
      resolve(base64);
    };
    reader.onerror = () => reject(new Error(`Failed to read file: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

/**
 * Handle file drop or file picker selection.
 * Reads allowed files and returns their name, size, and base64 content.
 *
 * @param files FileList from drop event or input element
 * @returns Array of uploaded file objects
 */
export async function handleFileDrop(files: FileList): Promise<UploadedFile[]> {
  const results: UploadedFile[] = [];
  const maxFileSize = 10 * 1024 * 1024; // 10 MB limit per file

  for (let i = 0; i < files.length; i++) {
    const file = files[i];

    // Check if file type is allowed
    if (!isAllowedFile(file.name)) {
      console.warn(`[FileUpload] Skipping unsupported file: ${file.name}`);
      continue;
    }

    // Check file size
    if (file.size > maxFileSize) {
      console.warn(`[FileUpload] File too large (${formatFileSize(file.size)}): ${file.name}`);
      continue;
    }

    try {
      const base64 = await readFileAsBase64(file);
      results.push({
        name: file.name,
        size: file.size,
        base64,
        type: file.type || ALLOWED_TYPES[getExtension(file.name)] || 'application/octet-stream',
      });
    } catch (err) {
      console.error(`[FileUpload] Error reading ${file.name}:`, err);
    }
  }

  return results;
}

/**
 * Format file size in human-readable form.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const size = bytes / Math.pow(k, i);

  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
