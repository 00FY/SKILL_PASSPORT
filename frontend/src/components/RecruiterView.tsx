import React from 'react';
import { PassportDocument, SkillPassportItem } from '../lib/types';
import { PassportSummary } from './PassportSummary';
import { ClaimList } from './ClaimList';
import { AuditDetails } from './AuditDetails';

interface RecruiterViewProps {
  passport: PassportDocument;
  onOpenSkill: (skill: SkillPassportItem) => void;
}

export const RecruiterView: React.FC<RecruiterViewProps> = ({ passport, onOpenSkill }) => (
  <div className="space-y-6">
    <PassportSummary passport={passport} />
    <ClaimList passport={passport} onOpenSkill={onOpenSkill} />
    <AuditDetails passport={passport} />
  </div>
);
