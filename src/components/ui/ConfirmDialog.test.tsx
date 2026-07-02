import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from './ConfirmDialog';

const baseProps = {
  title: 'Clear all search history?',
  body: 'Saved local searches will be removed.',
  confirmLabel: 'Clear all',
};

describe('ConfirmDialog', () => {
  it('focuses the cancel button on open and restores focus on close', () => {
    const outside = document.createElement('button');
    outside.textContent = 'outside';
    document.body.appendChild(outside);
    outside.focus();

    const { unmount } = render(
      <ConfirmDialog {...baseProps} onCancel={() => undefined} onConfirm={() => undefined} />,
    );

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    unmount();
    expect(outside).toHaveFocus();
    outside.remove();
  });

  it('cancels on Escape', () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...baseProps} onCancel={onCancel} onConfirm={() => undefined} />);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('cancels when the backdrop is clicked but not when the dialog body is clicked', () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...baseProps} onCancel={onCancel} onConfirm={() => undefined} />);

    fireEvent.mouseDown(screen.getByRole('dialog'));
    expect(onCancel).not.toHaveBeenCalled();

    fireEvent.mouseDown(screen.getByRole('dialog').parentElement as HTMLElement);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('keeps Tab focus inside the dialog', () => {
    render(<ConfirmDialog {...baseProps} onCancel={() => undefined} onConfirm={() => undefined} />);

    const cancel = screen.getByRole('button', { name: 'Cancel' });
    const confirm = screen.getByRole('button', { name: 'Clear all' });

    confirm.focus();
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(cancel).toHaveFocus();

    cancel.focus();
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
    expect(confirm).toHaveFocus();
  });

  it('locks body scroll while open', () => {
    const { unmount } = render(
      <ConfirmDialog {...baseProps} onCancel={() => undefined} onConfirm={() => undefined} />,
    );
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });
});
