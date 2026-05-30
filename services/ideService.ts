import { ApiClient } from './apiClient';

export class IdeService {
  static async compileProject(projectPath: string, board: string) {
    return ApiClient.post('/api/ide/compile', {
      project_path: projectPath,
      board: board
    });
  }
}
