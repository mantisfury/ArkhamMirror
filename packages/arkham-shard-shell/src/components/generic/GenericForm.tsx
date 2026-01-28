/**
 * GenericForm - Data-driven form component
 *
 * Renders a form with validation based on manifest ActionConfig.
 *
 * Shell Invariants:
 * - Non-authoritative: Only renders what config provides
 * - Surfaces errors: Displays validation and API errors to user
 * - Minimal logic: Validation via HTML5 attributes, no business logic
 */

import { useState, useCallback, FormEvent } from 'react';
import { useToast } from '../../context/ToastContext';
import { Icon } from '../common/Icon';
import type { ActionConfig, FormFieldConfig, SelectOption } from '../../types';
import { apiFetch } from '../../utils/api';

interface GenericFormProps {
  apiPrefix: string;
  action: ActionConfig;
  initialData?: Record<string, unknown>;
  onSuccess?: (result: unknown) => void;
  onCancel?: () => void;
}

interface FieldError {
  [fieldName: string]: string;
}

export function GenericForm({
  apiPrefix,
  action,
  initialData = {},
  onSuccess,
  onCancel,
}: GenericFormProps) {
  const { toast } = useToast();

  // Form state
  const [formData, setFormData] = useState<Record<string, unknown>>(() => {
    const initial: Record<string, unknown> = {};
    action.fields.forEach(field => {
      initial[field.name] = initialData[field.name] ?? field.default ?? '';
    });
    return initial;
  });

  const [errors, setErrors] = useState<FieldError>({});
  const [submitting, setSubmitting] = useState(false);

  // Handle field change
  const handleChange = useCallback((fieldName: string, value: unknown) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));
    // Clear error when user types
    if (errors[fieldName]) {
      setErrors(prev => {
        const next = { ...prev };
        delete next[fieldName];
        return next;
      });
    }
  }, [errors]);

  // Validate form
  const validateForm = useCallback((): boolean => {
    const newErrors: FieldError = {};

    action.fields.forEach(field => {
      const value = formData[field.name];

      // Required validation
      if (field.required && (value === '' || value === null || value === undefined)) {
        newErrors[field.name] = field.error_message || `${field.label} is required`;
        return;
      }

      // Skip further validation if empty and not required
      if (value === '' || value === null || value === undefined) return;

      // Type-specific validations
      if (field.type === 'number') {
        const num = Number(value);
        if (isNaN(num)) {
          newErrors[field.name] = 'Must be a valid number';
          return;
        }
        if (field.min !== undefined && num < field.min) {
          newErrors[field.name] = field.error_message || `Must be at least ${field.min}`;
          return;
        }
        if (field.max !== undefined && num > field.max) {
          newErrors[field.name] = field.error_message || `Must be at most ${field.max}`;
          return;
        }
      }

      if (field.type === 'email') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(String(value))) {
          newErrors[field.name] = field.error_message || 'Must be a valid email address';
          return;
        }
      }

      if (field.pattern) {
        try {
          const regex = new RegExp(field.pattern);
          if (!regex.test(String(value))) {
            newErrors[field.name] = field.error_message || 'Invalid format';
            return;
          }
        } catch {
          // Invalid regex pattern in config
          console.warn(`Invalid regex pattern in field ${field.name}: ${field.pattern}`);
        }
      }

      // Text min/max length
      if ((field.type === 'text' || field.type === 'textarea') && typeof value === 'string') {
        if (field.min !== undefined && value.length < field.min) {
          newErrors[field.name] = field.error_message || `Must be at least ${field.min} characters`;
          return;
        }
        if (field.max !== undefined && value.length > field.max) {
          newErrors[field.name] = field.error_message || `Must be at most ${field.max} characters`;
          return;
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [action.fields, formData]);

  // Handle submit
  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      toast.error('Please fix the form errors');
      return;
    }

    setSubmitting(true);

    try {
      const response = await apiFetch(`${apiPrefix}${action.endpoint}`, {
        method: action.method,
        body: JSON.stringify(formData),
      });

      const result = await response.json();

      if (!response.ok) {
        // Handle validation errors from server
        if (result.errors && typeof result.errors === 'object') {
          setErrors(result.errors as FieldError);
          toast.error('Please fix the form errors');
          return;
        }
        throw new Error(result.detail || result.message || 'Form submission failed');
      }

      toast.success(result.message || 'Success');
      onSuccess?.(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Form submission failed');
    } finally {
      setSubmitting(false);
    }
  }, [apiPrefix, action, formData, validateForm, toast, onSuccess]);

  return (
    <form className="generic-form" onSubmit={handleSubmit}>
      {action.description && (
        <p className="form-description">{action.description}</p>
      )}

      <div className="form-fields">
        {action.fields.map(field => (
          <FormField
            key={field.name}
            field={field}
            value={formData[field.name]}
            error={errors[field.name]}
            onChange={(value) => handleChange(field.name, value)}
            disabled={submitting}
          />
        ))}
      </div>

      <div className="form-actions">
        {onCancel && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          className="btn btn-primary"
          disabled={submitting}
        >
          {submitting ? (
            <>
              <Icon name="Loader2" size={16} className="spin" />
              Submitting...
            </>
          ) : (
            action.label
          )}
        </button>
      </div>
    </form>
  );
}

// ==== Sub-components ====

interface FormFieldProps {
  field: FormFieldConfig;
  value: unknown;
  error?: string;
  onChange: (value: unknown) => void;
  disabled: boolean;
}

function FormField({ field, value, error, onChange, disabled }: FormFieldProps) {
  const inputId = `field-${field.name}`;

  return (
    <div className={`form-field ${error ? 'has-error' : ''}`}>
      <label htmlFor={inputId}>
        {field.label}
        {field.required && <span className="required">*</span>}
      </label>

      {renderInput(field, value, inputId, onChange, disabled)}

      {error && (
        <span className="field-error">
          <Icon name="AlertCircle" size={14} />
          {error}
        </span>
      )}
    </div>
  );
}

function renderInput(
  field: FormFieldConfig,
  value: unknown,
  inputId: string,
  onChange: (value: unknown) => void,
  disabled: boolean
) {
  const commonProps = {
    id: inputId,
    name: field.name,
    disabled,
    required: field.required,
  };

  switch (field.type) {
    case 'textarea':
      return (
        <textarea
          {...commonProps}
          value={String(value || '')}
          onChange={(e) => onChange(e.target.value)}
          minLength={field.min}
          maxLength={field.max}
          rows={4}
        />
      );

    case 'number':
      return (
        <input
          {...commonProps}
          type="number"
          value={value === '' || value === undefined ? '' : String(value)}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          min={field.min}
          max={field.max}
        />
      );

    case 'email':
      return (
        <input
          {...commonProps}
          type="email"
          value={String(value || '')}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'select':
      return (
        <select
          {...commonProps}
          value={String(value || '')}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Select {field.label}...</option>
          {field.options?.map((opt: SelectOption) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );

    case 'text':
    default:
      return (
        <input
          {...commonProps}
          type="text"
          value={String(value || '')}
          onChange={(e) => onChange(e.target.value)}
          minLength={field.min}
          maxLength={field.max}
          pattern={field.pattern}
        />
      );
  }
}

// ==== Dialog Wrapper ====

interface GenericFormDialogProps extends GenericFormProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GenericFormDialog({
  isOpen,
  onClose,
  onSuccess,
  ...formProps
}: GenericFormDialogProps) {
  if (!isOpen) return null;

  const handleSuccess = (result: unknown) => {
    onSuccess?.(result);
    onClose();
  };

  return (
    <div className="generic-form-dialog-overlay" onClick={onClose}>
      <div className="generic-form-dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>{formProps.action.label}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close">
            <Icon name="X" size={20} />
          </button>
        </div>
        <div className="dialog-content">
          <GenericForm
            {...formProps}
            onSuccess={handleSuccess}
            onCancel={onClose}
          />
        </div>
      </div>
    </div>
  );
}
