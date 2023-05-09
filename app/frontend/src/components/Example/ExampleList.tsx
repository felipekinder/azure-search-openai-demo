import { Example } from "./Example";

import styles from "./Example.module.css";

export type ExampleModel = {
    text: string;
    value: string;
};

const EXAMPLES: ExampleModel[] = [
    {
        text: "Qual a missão da empresa?",
        value: "Qual a missão da E-Create?"
    },
    { text: "Qual o plano de saúde da empresa?", value: "Qual o plano de saúde da E-Create?" },
    {
        text: " A empresa tem normas e procedimentos para a conduta dos funcionários no ambiente de trabalho?",
        value: "A empresa tem normas e procedimentos para a conduta dos funcionários no ambiente de trabalho?"
    }
];

interface Props {
    onExampleClicked: (value: string) => void;
}

export const ExampleList = ({ onExampleClicked }: Props) => {
    return (
        <ul className={styles.examplesNavList}>
            {EXAMPLES.map((x, i) => (
                <li key={i}>
                    <Example text={x.text} value={x.value} onClick={onExampleClicked} />
                </li>
            ))}
        </ul>
    );
};
