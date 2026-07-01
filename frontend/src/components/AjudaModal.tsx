import type { LucideIcon } from 'lucide-react'
import {
  BadgeCheck,
  Calculator,
  ListChecks,
  Lock,
  Sparkles,
  TrendingUp,
} from 'lucide-react'

import Modal from './Modal'

interface AjudaModalProps {
  aberto: boolean
  onFechar: () => void
}

/**
 * Modal de ajuda — explica, em linguagem de produto (para um leitor não-técnico,
 * até diretoria), como funciona o módulo de Triagem.
 *
 * ⚠️ CONTEÚDO PROVISÓRIO: o texto abaixo é um rascunho só para dar forma ao
 * visual. Substitua os campos `texto`/`itens` de cada seção pelo conteúdo final
 * — a estrutura (seções com ícone + título + corpo) já está pronta.
 */
interface SecaoAjuda {
  icone: LucideIcon
  titulo: string
  texto?: string
  itens?: string[]
}

const SECOES: SecaoAjuda[] = [
  {
    icone: Sparkles,
    titulo: 'O que é',
    texto:
      'A Triagem recebe os currículos de uma vaga e devolve, para cada candidato, ' +
      'uma leitura estruturada: o quanto ele adere ao perfil, os pontos de destaque, ' +
      'as lacunas e uma recomendação clara (avançar, revisar ou não avançar). O objetivo ' +
      'é poupar horas de leitura manual e padronizar o critério de avaliação.',
  },
  {
    icone: ListChecks,
    titulo: 'Como funciona (passo a passo)',
    itens: [
      'Você cadastra a vaga colando a descrição e a IA propõe os critérios de avaliação.',
      'Você confere e ajusta os pesos e o que é decisivo, com linguagem simples.',
      'Você sobe os currículos (PDF ou texto); eles entram numa fila e são avaliados.',
      'O sistema devolve um ranking, com a justificativa de cada nota e a recomendação.',
    ],
  },
  {
    icone: Calculator,
    titulo: 'Como a nota é calculada',
    texto:
      'A IA apenas lê o currículo e dá evidências; quem calcula a nota é o sistema, ' +
      'aplicando a régua de pesos que você definiu, de forma determinística e auditável. ' +
      'Isso significa que a mesma régua aplicada ao mesmo currículo gera sempre a mesma ' +
      'nota, e você consegue ver exatamente de onde cada ponto veio.',
  },
  {
    icone: TrendingUp,
    titulo: 'Custo e desempenho',
    texto:
      'A aba Métricas mostra o que normalmente fica invisível: o quanto a IA decide ' +
      'sozinha, quanto custa cada etapa (em dólar e em real) e o tempo de resposta. ' +
      'É a evidência de que a automação tem impacto medido, não apenas promessa.',
  },
  {
    icone: Lock,
    titulo: 'LGPD e anti-viés',
    texto:
      'Antes de qualquer dado ir para a IA, informações pessoais sensíveis são removidas ' +
      '(nome, contato e marcadores que poderiam gerar viés). A avaliação é feita sobre ' +
      'competências e evidências, não sobre quem é a pessoa.',
  },
]

export default function AjudaModal({ aberto, onFechar }: AjudaModalProps) {
  return (
    <Modal titulo="Como funciona a Triagem" aberto={aberto} onFechar={onFechar} medio>
      <div className="ajuda-conteudo">
        <div className="ajuda-rascunho">
          <BadgeCheck size={14} /> Conteúdo provisório. Você vai personalizar este texto.
        </div>
        {SECOES.map(({ icone: Icone, titulo, texto, itens }) => (
          <section key={titulo} className="ajuda-secao">
            <div className="ajuda-secao-icone">
              <Icone size={18} strokeWidth={2} />
            </div>
            <div className="ajuda-secao-corpo">
              <h3 className="ajuda-secao-titulo">{titulo}</h3>
              {texto && <p className="ajuda-secao-texto">{texto}</p>}
              {itens && (
                <ol className="ajuda-passos">
                  {itens.map((item, i) => (
                    <li key={i}>
                      <span className="ajuda-passo-num">{i + 1}</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        ))}
      </div>
    </Modal>
  )
}
