import { Example } from "./Example";

import styles from "./Example.module.css";

export type ExampleModel = {
    text: string;
    value: string;
};

const EXAMPLES: ExampleModel[] = [
    {
        text: "Qual a missão da empresa?",
        value: "Qual a missão da empresa?"
    },
    { text: "Qual o plano de saúde da empresa?", value: "Qual o plano de saúde da empresa?" },
    { text: "O que é o Termo do Confidencialidade?", value: "O que é o Termo do Confidencialidade?" }
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
