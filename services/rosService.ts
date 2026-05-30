import { ApiClient } from './apiClient';

export class RosService {
  static async launchCore() {
    return ApiClient.post('/api/ros/launch_core');
  }

  static async stopCore() {
    return ApiClient.post('/api/ros/stop_core');
  }
}
