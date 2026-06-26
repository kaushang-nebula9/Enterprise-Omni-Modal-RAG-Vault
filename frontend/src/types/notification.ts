export type NotificationType =
  | 'role_assigned'
  | 'document_access_direct'
  | 'document_access_inherited_hierarchy'
  | 'document_access_inherited_department'
  | 'department_added'
  | 'evaluation_completed';

export interface Notification {
  id: string;
  user_id: string;
  tenant_id: string;
  type: NotificationType;
  message: string;
  related_document_id?: string;
  related_role_id?: string;
  related_department_id?: string;
  related_evaluation_id?: string;
  is_read: boolean;
  created_at: string;
}

