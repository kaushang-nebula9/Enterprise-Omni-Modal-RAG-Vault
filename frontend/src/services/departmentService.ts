import api from "./api";

export interface DepartmentResponse {
  id: string;
  name: string;
  tenant_id: string;
  created_at: string;
}

export interface CreateDepartmentPayload {
  name: string;
}

export interface UpdateDepartmentPayload {
  name: string;
}

export const departmentService = {
  getDepartments: async (): Promise<DepartmentResponse[]> => {
    const response = await api.get("/api/v1/departments");
    return response.data;
  },

  createDepartment: async (
    data: CreateDepartmentPayload,
  ): Promise<DepartmentResponse> => {
    const response = await api.post("/api/v1/departments", data);
    return response.data;
  },

  updateDepartment: async (
    id: string,
    data: UpdateDepartmentPayload,
  ): Promise<DepartmentResponse> => {
    const response = await api.patch(`/api/v1/departments/${id}`, data);
    return response.data;
  },

  deleteDepartment: async (id: string): Promise<{ message: string }> => {
    const response = await api.delete(`/api/v1/departments/${id}`);
    return response.data;
  },
};
